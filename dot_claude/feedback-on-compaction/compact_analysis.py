#!/usr/bin/env python3
"""Read-only Claude Code / Codex context-compaction analysis.

The source logs are never modified.  Output is written only below --out.
Only token counts and structural metadata are exported; transcript text is not.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Iterable


DEFAULT_PRICES = {
    # USD / 1M tokens, effective 2026-08-12.  Edit via --prices.
    "claude-sonnet-5": {"input": 2.0, "cache_read": 0.2, "cache_write_5m": 2.5, "cache_write_1h": 4.0, "output": 10.0},
    "claude-opus-5": {"input": 5.0, "cache_read": 0.5, "cache_write_5m": 6.25, "cache_write_1h": 10.0, "output": 25.0},
    "gpt-5.6-sol": {"input": 5.0, "cache_read": 0.5, "cache_write": 6.25, "output": 30.0},
    "gpt-5.6-terra": {"input": 2.0, "cache_read": 0.2, "cache_write": 2.5, "output": 12.0},
    "gpt-5.4": {"input": 2.5, "cache_read": 0.25, "cache_write": 3.125, "output": 15.0},
    "generic": {"input": 1.0, "cache_read": 0.1, "cache_write": 1.25, "output": 5.0},
}

TOKEN_KEYS = ("uncached_input", "cache_read", "cache_write", "output")


@dataclass
class Request:
    source: str
    session: str
    path: str
    timestamp: str
    model: str
    request_id: str
    context_tokens: int
    uncached_input: int
    cache_read: int
    cache_write: int
    cache_write_5m: int
    cache_write_1h: int
    output: int
    reasoning_output: int
    tool_result_tokens_est: float = 0.0
    reread_tokens_est: float = 0.0
    mcp_result_tokens_est: float = 0.0
    context_delta: int = 0


@dataclass
class Compact:
    source: str
    session: str
    path: str
    timestamp: str
    trigger: str
    pre_tokens: int
    post_tokens: int
    compact_payload_tokens: int
    fixed_context_tokens_est: float
    summary_tokens_est: float
    summary_tokens_low: float
    summary_tokens_high: float
    summary_usage_observed: bool
    reread_tokens_est: float = 0.0
    tool_tokens_after_est: float = 0.0
    mcp_tokens_after_est: float = 0.0
    requests_to_pre_size: int = -1
    requests_observed: int = 0
    growth_per_request: float = 0.0
    gross_saved_token_requests: float = 0.0
    net_saved_token_requests_est: float = 0.0
    break_even_requests: float = math.nan
    break_even_requests_low: float = math.nan
    break_even_requests_high: float = math.nan
    break_even_requests_summary_uncached: float = math.nan
    break_even_before_pre_size: bool = False
    break_even_before_next_compact: bool = False
    compact_overhead_usd_est: float = 0.0
    model: str = "generic"


def parse_ts(value: str) -> datetime:
    if not value:
        return datetime.min
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def text_chars(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return sum(text_chars(x) for x in value)
    if isinstance(value, dict):
        return sum(text_chars(v) for k, v in value.items() if k not in {"thinking", "signature"})
    return 0


def content_types(message: dict[str, Any]) -> list[str]:
    content = message.get("content") or []
    if isinstance(content, str):
        return ["text"]
    return [str(x.get("type")) for x in content if isinstance(x, dict)]


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    at = (len(values) - 1) * q
    lo, hi = math.floor(at), math.ceil(at)
    if lo == hi:
        return values[lo]
    return values[lo] * (hi - at) + values[hi] * (at - lo)


def median(values: Iterable[float]) -> float:
    seq = list(values)
    return statistics.median(seq) if seq else 0.0


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def extract_tool_metadata(rows: list[dict[str, Any]]) -> tuple[dict[str, tuple[str, str]], dict[int, tuple[str, str, int]]]:
    """Return tool_use_id metadata and result metadata indexed by row.

    Paths are retained only in memory to identify repeated reads; they are never
    exported, because transcript/tool arguments can contain private material.
    """
    uses: dict[str, tuple[str, str]] = {}
    results: dict[int, tuple[str, str, int]] = {}
    for idx, row in enumerate(rows):
        msg = row.get("message") or {}
        content = msg.get("content") or []
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_use":
                name = str(item.get("name") or "")
                inp = item.get("input") or {}
                arg = json.dumps(inp, ensure_ascii=False, sort_keys=True)
                uses[str(item.get("id"))] = (name, arg)
            elif item.get("type") == "tool_result":
                tool_id = str(item.get("tool_use_id") or "")
                name, arg = uses.get(tool_id, ("", ""))
                results[idx] = (name, arg, text_chars(item.get("content")))
    return uses, results


def is_mcp(name: str) -> bool:
    name = name.lower()
    return "mcp" in name or name.startswith("mcp__") or "unity" in name


def read_signature(name: str, arg: str) -> str:
    low = name.lower()
    readish = any(x in low for x in ("read", "open", "view", "grep", "glob", "find"))
    shell_read = any(x in arg.lower() for x in ("get-content", "select-string", " rg ", "rg --", "type "))
    if not (readish or shell_read):
        return ""
    # A stable digest would be ideal, but avoiding another import keeps the CSV
    # completely path-free.  The argument itself stays in memory only.
    return arg


def parse_claude_file(path: Path) -> tuple[list[Request], list[Compact]]:
    rows = read_jsonl(path)
    session = path.stem if "subagents" not in path.parts else f"{path.parents[1].name}/{path.stem}"
    _, tool_results = extract_tool_metadata(rows)

    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for idx, row in enumerate(rows):
        if row.get("type") == "assistant":
            msg = row.get("message") or {}
            rid = str(row.get("requestId") or msg.get("id") or f"{idx}")
            grouped[rid].append((idx, row))

    selected: list[tuple[int, Request]] = []
    for rid, variants in grouped.items():
        # Streaming snapshots repeat the same request.  The terminal snapshot
        # has stop_reason; max output_tokens is a safe fallback.
        idx, row = max(
            variants,
            key=lambda pair: (
                (pair[1].get("message") or {}).get("stop_reason") is not None,
                ((pair[1].get("message") or {}).get("usage") or {}).get("output_tokens", 0) or 0,
                pair[0],
            ),
        )
        msg = row.get("message") or {}
        usage = msg.get("usage") or {}
        creation = usage.get("cache_creation") or {}
        write_5m = int(creation.get("ephemeral_5m_input_tokens", 0) or 0)
        write_1h = int(creation.get("ephemeral_1h_input_tokens", 0) or 0)
        write = int(usage.get("cache_creation_input_tokens", 0) or 0)
        if not write_5m and not write_1h:
            write_5m = write
        uncached = int(usage.get("input_tokens", 0) or 0)
        cached = int(usage.get("cache_read_input_tokens", 0) or 0)
        request = Request(
            source="claude",
            session=session,
            path=str(path),
            timestamp=str(row.get("timestamp") or ""),
            model=str(msg.get("model") or "generic"),
            request_id=rid,
            context_tokens=uncached + write + cached,
            uncached_input=uncached,
            cache_read=cached,
            cache_write=write,
            cache_write_5m=write_5m,
            cache_write_1h=write_1h,
            output=int(usage.get("output_tokens", 0) or 0),
            reasoning_output=0,
        )
        selected.append((idx, request))
    selected.sort(key=lambda x: x[0])

    # Estimate how non-model context growth divides between tool/MCP results.
    # Token totals are observed; allocation by result character share is an estimate.
    seen_reads: set[str] = set()
    prev_idx = -1
    prev: Request | None = None
    for idx, req in selected:
        if prev is None:
            prev_idx, prev = idx, req
            continue
        delta = req.context_tokens - prev.context_tokens
        req.context_delta = delta
        residual = max(0, delta - prev.output)
        candidates = [(j, meta) for j, meta in tool_results.items() if prev_idx < j < idx]
        total_chars = sum(meta[2] for _, meta in candidates)
        if total_chars:
            tool_tokens = residual
            req.tool_result_tokens_est = tool_tokens
            req.mcp_result_tokens_est = tool_tokens * sum(meta[2] for _, meta in candidates if is_mcp(meta[0])) / total_chars
            reread_chars = 0
            for _, (name, arg, chars) in candidates:
                sig = read_signature(name, arg)
                if sig and sig in seen_reads:
                    reread_chars += chars
                if sig:
                    seen_reads.add(sig)
            req.reread_tokens_est = tool_tokens * reread_chars / total_chars
        prev_idx, prev = idx, req

    compacts: list[Compact] = []
    for idx, row in enumerate(rows):
        if row.get("type") != "system" or row.get("subtype") != "compact_boundary":
            continue
        meta = row.get("compactMetadata") or {}
        post = int(meta.get("postTokens", 0) or 0)
        # No summary usage exists in the transcript.  postTokens is an upper
        # bound on summary output because fixed/reinjected context may be included.
        compacts.append(Compact(
            source="claude", session=session, path=str(path), timestamp=str(row.get("timestamp") or ""),
            trigger=str(meta.get("trigger") or "unknown"), pre_tokens=int(meta.get("preTokens", 0) or 0),
            post_tokens=0, compact_payload_tokens=post, fixed_context_tokens_est=0,
            summary_tokens_est=post * 0.75,
            summary_tokens_low=post * 0.5, summary_tokens_high=post,
            summary_usage_observed=False,
        ))
    return [r for _, r in selected], compacts


def parse_codex_file(path: Path) -> tuple[list[Request], list[Compact]]:
    rows = read_jsonl(path)
    session = path.stem
    model = "generic"
    for row in rows:
        if row.get("type") == "turn_context":
            model = str((row.get("payload") or {}).get("model") or model)
            break
    requests: list[Request] = []
    for idx, row in enumerate(rows):
        payload = row.get("payload") or {}
        if row.get("type") != "event_msg" or payload.get("type") != "token_count":
            continue
        info = payload.get("info") or {}
        usage = info.get("last_token_usage") or {}
        input_total = int(usage.get("input_tokens", 0) or 0)
        if input_total == 0 and int(usage.get("output_tokens", 0) or 0) == 0:
            continue
        cached = int(usage.get("cached_input_tokens", 0) or 0)
        write = int(usage.get("cache_write_input_tokens", 0) or 0)
        requests.append(Request(
            source="codex", session=session, path=str(path), timestamp=str(row.get("timestamp") or ""),
            model=model, request_id=f"{session}:{idx}", context_tokens=input_total,
            uncached_input=max(0, input_total - cached), cache_read=cached, cache_write=write,
            cache_write_5m=write, cache_write_1h=0,
            output=int(usage.get("output_tokens", 0) or 0),
            reasoning_output=int(usage.get("reasoning_output_tokens", 0) or 0),
        ))
    for prev, cur in zip(requests, requests[1:]):
        cur.context_delta = cur.context_tokens - prev.context_tokens
        # Codex rollouts do not expose per-result token counts.  This is an upper
        # bound for all newly carried input after subtracting prior model output.
        cur.tool_result_tokens_est = max(0, cur.context_delta - prev.output)

    compacts: list[Compact] = []
    for idx, row in enumerate(rows):
        if row.get("type") != "compacted":
            continue
        ts = str(row.get("timestamp") or "")
        before = [r for r in requests if parse_ts(r.timestamp) < parse_ts(ts)]
        after = [r for r in requests if parse_ts(r.timestamp) > parse_ts(ts)]
        pre = before[-1].context_tokens if before else 0
        post = after[0].context_tokens if after else 0
        replacement = (row.get("payload") or {}).get("replacement_history") or []
        chars = text_chars(replacement)
        # New Claude/OpenAI coding tokenizers vary by content.  3-5 chars/token
        # is deliberately reported as a range, never as an observed count.
        summary_est = chars / 4.0
        compacts.append(Compact(
            source="codex", session=session, path=str(path), timestamp=ts, trigger="automatic/unknown",
            pre_tokens=pre, post_tokens=post, compact_payload_tokens=0,
            fixed_context_tokens_est=max(0, post - summary_est), summary_tokens_est=summary_est,
            summary_tokens_low=chars / 5.0, summary_tokens_high=chars / 3.0,
            summary_usage_observed=False, model=model,
        ))
    return requests, compacts


def price_for(model: str, prices: dict[str, dict[str, float]]) -> dict[str, float]:
    if model in prices:
        return prices[model]
    low = model.lower()
    for key in prices:
        if key != "generic" and key in low:
            return prices[key]
    return prices["generic"]


def enrich_compacts(requests: list[Request], compacts: list[Compact], prices: dict[str, dict[str, float]]) -> None:
    by_session: dict[tuple[str, str], list[Request]] = defaultdict(list)
    by_compact: dict[tuple[str, str], list[Compact]] = defaultdict(list)
    for req in requests:
        by_session[(req.source, req.session)].append(req)
    for event in compacts:
        by_compact[(event.source, event.session)].append(event)

    for key, events in by_compact.items():
        reqs = sorted(by_session.get(key, []), key=lambda r: parse_ts(r.timestamp))
        events.sort(key=lambda e: parse_ts(e.timestamp))
        for event_idx, event in enumerate(events):
            start = parse_ts(event.timestamp)
            end = parse_ts(events[event_idx + 1].timestamp) if event_idx + 1 < len(events) else datetime.max
            after = [r for r in reqs if start < parse_ts(r.timestamp) < end]
            if not after:
                continue
            event.model = after[0].model or event.model
            if event.source == "claude":
                # compactMetadata.postTokens is only the compacted payload.  The
                # next full request also has reinjected system/project context.
                event.post_tokens = after[0].context_tokens
                event.fixed_context_tokens_est = max(0, event.post_tokens - event.compact_payload_tokens)
            event.requests_observed = len(after)
            event.reread_tokens_est = sum(r.reread_tokens_est for r in after)
            event.tool_tokens_after_est = sum(r.tool_result_tokens_est for r in after)
            event.mcp_tokens_after_est = sum(r.mcp_result_tokens_est for r in after)
            regained = next((i + 1 for i, r in enumerate(after) if r.context_tokens >= event.pre_tokens), -1)
            event.requests_to_pre_size = regained
            usable = after[:regained] if regained > 0 else after
            deltas = [max(0, r.context_delta) for r in usable[1:] if r.context_delta > 0]
            event.growth_per_request = median(deltas)
            saved = max(0, event.pre_tokens - event.post_tokens)
            event.gross_saved_token_requests = saved * len(usable)
            # Re-read material remains in every later request.  Introductions are
            # approximated at each request and accumulated as context area.
            cumulative_reread = 0.0
            net_area = 0.0
            for r in usable:
                cumulative_reread += r.reread_tokens_est
                net_area += max(0.0, saved - cumulative_reread)
            event.net_saved_token_requests_est = net_area

            price = price_for(event.model, prices)
            p_read = price.get("cache_read", price.get("input", 1.0) * 0.1)
            p_output = price.get("output", 5.0)
            # Summary input is not logged.  Default assumes the pre-context is a
            # cache hit; summary output uses the explicitly labelled estimate.
            summary_cost = (event.pre_tokens * p_read + event.summary_tokens_est * p_output) / 1_000_000
            first_write = after[0].cache_write
            p_write = price.get("cache_write_1h", price.get("cache_write", price.get("input", 1.0) * 1.25))
            reset_cost = first_write * p_write / 1_000_000
            reread_intro_cost = event.reread_tokens_est * price.get("input", 1.0) / 1_000_000
            event.compact_overhead_usd_est = summary_cost + reset_cost + reread_intro_cost
            saving_per_request = saved * p_read / 1_000_000
            event.break_even_requests = event.compact_overhead_usd_est / saving_per_request if saving_per_request else math.inf
            low_cost = event.compact_overhead_usd_est + (event.summary_tokens_low - event.summary_tokens_est) * p_output / 1_000_000
            high_cost = event.compact_overhead_usd_est + (event.summary_tokens_high - event.summary_tokens_est) * p_output / 1_000_000
            event.break_even_requests_low = low_cost / saving_per_request if saving_per_request else math.inf
            event.break_even_requests_high = high_cost / saving_per_request if saving_per_request else math.inf
            uncached_summary_cost = event.compact_overhead_usd_est + event.pre_tokens * (price.get("input", 1.0) - p_read) / 1_000_000
            event.break_even_requests_summary_uncached = uncached_summary_cost / saving_per_request if saving_per_request else math.inf
            event.break_even_before_pre_size = event.break_even_requests <= len(usable)
            event.break_even_before_next_compact = event.break_even_requests <= len(after)


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def svg_chart(path: Path, title: str, series: list[tuple[str, list[tuple[float, float]], str]], x_label: str, y_label: str) -> None:
    width, height = 1000, 560
    left, right, top, bottom = 90, 30, 55, 70
    points = [p for _, values, _ in series for p in values]
    if not points:
        return
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(0.0, min(ys)), max(ys)
    if xmax == xmin: xmax += 1
    if ymax == ymin: ymax += 1
    sx = lambda x: left + (x - xmin) / (xmax - xmin) * (width - left - right)
    sy = lambda y: height - bottom - (y - ymin) / (ymax - ymin) * (height - top - bottom)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="#fff"/>',
           f'<text x="{width/2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="20">{escape(title)}</text>']
    for i in range(6):
        yv = ymin + (ymax - ymin) * i / 5
        y = sy(yv)
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" stroke="#ddd"/>')
        out.append(f'<text x="{left-8}" y="{y+4:.1f}" text-anchor="end" font-family="sans-serif" font-size="12">{yv:,.0f}</text>')
    out.append(f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#222"/>')
    out.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#222"/>')
    for label, values, color in series:
        coords = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in values)
        out.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2"/>')
    out.append(f'<text x="{width/2}" y="{height-18}" text-anchor="middle" font-family="sans-serif" font-size="14">{escape(x_label)}</text>')
    out.append(f'<text x="18" y="{height/2}" transform="rotate(-90 18 {height/2})" text-anchor="middle" font-family="sans-serif" font-size="14">{escape(y_label)}</text>')
    out.append('</svg>')
    path.write_text("\n".join(out), encoding="utf-8")


def make_charts(out: Path, requests: list[Request], compacts: list[Compact]) -> None:
    colors = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c", "#0891b2", "#4b5563", "#be123c"]
    compact_sessions = {(e.source, e.session) for e in compacts}
    series = []
    for n, key in enumerate(sorted(compact_sessions)):
        values = [(i + 1, r.context_tokens / 1000) for i, r in enumerate(requests) if (r.source, r.session) == key]
        if values:
            series.append((f"{key[0]}:{key[1][:8]}", values, colors[n % len(colors)]))
    svg_chart(out / "context_size_over_time.svg", "Context size over model requests (compact sessions)", series, "model request index", "context (k tokens)")

    prepost = []
    for i, e in enumerate(compacts):
        prepost.extend([(i * 3 + 1, e.pre_tokens / 1000), (i * 3 + 2, e.post_tokens / 1000), (i * 3 + 3, math.nan)])
    prepost = [(x, y) for x, y in prepost if not math.isnan(y)]
    svg_chart(out / "compact_pre_post.svg", "Compact events: pre vs post", [("events", prepost, "#2563eb")], "event pair", "context (k tokens)")

    be = [(i + 1, min(e.break_even_requests, 100) if math.isfinite(e.break_even_requests) else 100) for i, e in enumerate(compacts)]
    svg_chart(out / "break_even_requests.svg", "Estimated break-even request count (capped at 100)", [("break-even", be, "#dc2626")], "compact event", "model requests")

    representative = sorted(compacts, key=lambda e: e.pre_tokens)[len(compacts)//2] if compacts else None
    if representative:
        price = price_for(representative.model, DEFAULT_PRICES)
        saved = max(0, representative.pre_tokens - representative.post_tokens)
        per = saved * price.get("cache_read", 0.1) / 1_000_000
        curve = [(n, representative.compact_overhead_usd_est - n * per) for n in range(0, 51)]
        svg_chart(out / "cumulative_cost_difference.svg", "Compact minus no-compact cumulative cost (representative event)", [("delta USD", curve, "#059669")], "model requests after compact", "USD; negative = compact wins")


def strategy_table(requests: list[Request], thresholds: list[int], reset_tokens: int) -> list[dict[str, Any]]:
    """Replay observed positive context increments with a synthetic compact reset.

    This is explicitly a same-actions counterfactual, not an observation of model
    behaviour beyond the original window.
    """
    result = []
    sessions: dict[tuple[str, str], list[Request]] = defaultdict(list)
    for r in requests:
        sessions[(r.source, r.session)].append(r)
    for threshold in thresholds:
        areas, counts, reaches = [], [], []
        for reqs in sessions.values():
            if len(reqs) < 3:
                continue
            context = reqs[0].context_tokens
            area = 0.0
            count = 0
            for prev, cur in zip(reqs, reqs[1:]):
                context += max(0, cur.context_tokens - prev.context_tokens)
                if context >= threshold:
                    context = reset_tokens
                    count += 1
                area += context
            areas.append(area)
            counts.append(count)
            reaches.append(max(r.context_tokens for r in reqs) >= threshold)
        reached_counts = [count for count, reached in zip(counts, reaches) if reached]
        reached_areas = [area for area, reached in zip(areas, reaches) if reached]
        replay_counts = [count for count in counts if count > 0]
        replay_areas = [area for area, count in zip(areas, counts) if count > 0]
        result.append({
            "threshold_tokens": threshold,
            "sessions": len(areas),
            "sessions_reaching_observed": sum(reaches),
            "sessions_reaching_replay": len(replay_counts),
            "reset_tokens": reset_tokens,
            "median_compacts_replay": median(replay_counts),
            "median_cached_context_area_replay": median(replay_areas),
            "status": "counterfactual_same_actions",
        })
    return result


def session_table(requests: list[Request], compacts: list[Compact]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Request]] = defaultdict(list)
    compact_counts = Counter((e.source, e.session) for e in compacts)
    for request in requests:
        grouped[(request.source, request.session)].append(request)
    result = []
    for (source, session), reqs in grouped.items():
        reqs.sort(key=lambda r: parse_ts(r.timestamp))
        positive = [r.context_delta for r in reqs if r.context_delta > 0]
        tool_per_request = sum(r.tool_result_tokens_est for r in reqs) / len(reqs)
        mcp_per_request = sum(r.mcp_result_tokens_est for r in reqs) / len(reqs)
        mcp_share = sum(r.mcp_result_tokens_est for r in reqs) / max(1, sum(r.tool_result_tokens_est for r in reqs))
        growth = median(positive)
        if mcp_per_request >= 150 or mcp_share >= 0.15:
            cluster = "mcp_heavy"
        elif growth >= 3_000:
            cluster = "rapid_growth"
        elif len(reqs) >= 30:
            cluster = "steady_long"
        else:
            cluster = "short_normal"
        result.append({
            "source": source, "session": session, "model": Counter(r.model for r in reqs).most_common(1)[0][0],
            "request_count": len(reqs), "compact_count": compact_counts[(source, session)],
            "max_context_tokens": max(r.context_tokens for r in reqs),
            "median_positive_growth_per_request": growth,
            "tool_result_tokens_per_request_est": tool_per_request,
            "mcp_result_tokens_per_request_est": mcp_per_request,
            "mcp_share_est": mcp_share, "cluster": cluster,
        })
    return result


def render_report(out: Path, requests: list[Request], compacts: list[Compact], strategies: list[dict[str, Any]], sessions: list[dict[str, Any]]) -> None:
    by_source = Counter(r.source for r in requests)
    compact_by_source = Counter(e.source for e in compacts)
    usable_events = [e for e in compacts if e.post_tokens > 0]
    pre = [e.pre_tokens for e in usable_events]
    post = [e.post_tokens for e in usable_events]
    be = [e.break_even_requests for e in compacts if math.isfinite(e.break_even_requests)]
    be_uncached = [e.break_even_requests_summary_uncached for e in compacts if math.isfinite(e.break_even_requests_summary_uncached)]
    growth = [e.growth_per_request for e in compacts if e.growth_per_request > 0]
    mcp_share = [e.mcp_tokens_after_est / e.tool_tokens_after_est for e in compacts if e.mcp_tokens_after_est > 0 and e.tool_tokens_after_est > 0]
    claude_events = [e for e in usable_events if e.source == "claude"]
    codex_events = [e for e in usable_events if e.source == "codex"]
    claude_fixed = [e.fixed_context_tokens_est for e in claude_events if e.fixed_context_tokens_est > 0]
    codex_fixed = [e.fixed_context_tokens_est for e in codex_events if e.fixed_context_tokens_est > 0]
    lines = [
        "# Context compaction analysis (generated)", "",
        "Generated from local logs in read-only mode. Transcript text and tool arguments are not exported.", "",
        "## Dataset", "",
        f"- Model requests: Claude {by_source['claude']:,}; Codex {by_source['codex']:,}",
        f"- Compact events: Claude {compact_by_source['claude']}; Codex {compact_by_source['codex']}",
        f"- Pre-compact context: median {median(pre):,.0f}, range {min(pre) if pre else 0:,}–{max(pre) if pre else 0:,}",
        f"- Post-compact full context: Claude median {median(e.post_tokens for e in claude_events):,.0f}; Codex median {median(e.post_tokens for e in codex_events):,.0f}",
        f"- Reinjected/fixed context estimate: Claude median {median(claude_fixed):,.0f}; Codex median {median(codex_fixed):,.0f} tokens",
        f"- Positive context growth/request after compact: median {median(growth):,.0f} tokens",
        f"- Estimated MCP share of tool-result carry-in: median {median(mcp_share)*100:.1f}% (available events; character-allocation estimate)", "",
        "## Break-even summary", "",
        f"- Estimated break-even: median {median(be):.1f} requests; p25 {percentile(be, .25):.1f}; p75 {percentile(be, .75):.1f}.",
        f"- If the unlogged summary input is fully uncached instead: median {median(be_uncached):.1f} requests (sensitivity bound).",
        f"- Events breaking even before returning to the old pre-size: {sum(e.break_even_before_pre_size for e in usable_events)}/{len(usable_events)}.",
        f"- Events breaking even before the next compact/end: {sum(e.break_even_before_next_compact for e in usable_events)}/{len(usable_events)}.",
        "- This estimate prices the unlogged summary input as a cache read and summary output at the model output rate.",
        "- Fixed project/system context cancels in the A-vs-B comparison. It is not counted as a compact saving.", "",
        "- Current OpenAI GPT-5.4/5.6 pricing doubles input for prompts above 272k; the threshold replay reports token-area only and does not hide this price discontinuity.", "",
        "## Price assumptions (USD/MTok, retrieved 2026-08-12)", "",
        "- Claude Sonnet 5 introductory: input 2.00, 5m write 2.50, 1h write 4.00, read 0.20, output 10.00 (through 2026-08-31).",
        "- Claude Opus 5: input 5.00, 5m write 6.25, 1h write 10.00, read 0.50, output 25.00.",
        "- GPT-5.6 Sol: input 5.00, cached input 0.50, output 30.00; cache-write estimate is editable and set to 1.25x input.",
        "- GPT-5.4: input 2.50, cached input 0.25, output 15.00.",
        "- Claude source: https://platform.claude.com/docs/en/about-claude/pricing",
        "- OpenAI source: https://developers.openai.com/api/docs/models/compare",
        "- These are API-equivalent prices for comparison, not a claim about Claude Code/Codex subscription billing or quota accounting.", "",
        "## Observability", "",
        "| Quantity | Status | Method |", "|---|---|---|",
        "| Uncached/cache-read/cache-write/model-output | observed | request usage records, de-duplicated by request ID for Claude |",
        "| Context size | observed | Claude: input + cache creation + cache read; Codex: total input |",
        "| Compact pre/post full context | observed | last request before / first request after |",
        "| Claude compact payload | observed | compactMetadata.postTokens; excludes reinjected fixed context |",
        "| Compact summarization usage | unknown | absent from ordinary and cumulative usage logs |",
        "| Compact summary tokens | estimated range | Claude: 0.5–1.0 × postTokens; Codex: replacement text at 3–5 chars/token |",
        "| Tool-result carry-in | estimated | positive context delta minus previous model output |",
        "| Re-read tokens | estimated (Claude only) | repeated read-like tool arguments, allocated by result character share |",
        "| Causal no-compact behaviour above observed window | unknown | threshold replay assumes identical actions |", "",
        "## Threshold replay", "",
        "| Threshold | Observed reach | Same-actions replay reach | Median synthetic compacts | Median context×request |", "|---:|---:|---:|---:|---:|",
    ]
    for row in strategies:
        lines.append(f"| {row['threshold_tokens']/1000:.0f}k | {row['sessions_reaching_observed']} | {row['sessions_reaching_replay']} | {row['median_compacts_replay']:.1f} | {row['median_cached_context_area_replay']:,.0f} |")
    lines += ["", "## Session clusters", "", "| Cluster | Sessions | Median requests | Median max context | Median positive growth/request |", "|---|---:|---:|---:|---:|"]
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sessions:
        clusters[row["cluster"]].append(row)
    for name, rows in sorted(clusters.items()):
        lines.append(f"| {name} | {len(rows)} | {median(float(r['request_count']) for r in rows):.0f} | {median(float(r['max_context_tokens']) for r in rows):,.0f} | {median(float(r['median_positive_growth_per_request']) for r in rows):,.0f} |")
    lines += ["", "Cluster labels are operational heuristics, not learned semantic classes: MCP-heavy means ≥150 estimated MCP-result tokens/request or ≥15% of tool carry-in; rapid-growth means median positive growth ≥3k/request.", "", "## Files", "", "- `compact_events.csv`: one row per compact event", "- `model_requests.csv`: token usage per de-duplicated request", "- `session_summary.csv`: session variation and operational cluster", "- `threshold_strategy.csv`: same-actions threshold replay", "- SVG charts: context trajectory, compact pre/post, cumulative cost delta, break-even", ""]
    out.joinpath("report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--claude-root", type=Path, default=Path.home() / ".claude" / "projects")
    parser.add_argument("--codex-root", type=Path, default=Path.home() / ".codex" / "sessions")
    parser.add_argument("--project-filter", default="", help="substring filter for Claude JSONL paths")
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("output"))
    parser.add_argument("--prices", type=Path, help="JSON override for USD/1M-token prices")
    parser.add_argument("--thresholds", default="200000,250000,300000,400000,500000")
    args = parser.parse_args()
    prices = DEFAULT_PRICES
    if args.prices:
        prices = json.loads(args.prices.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)

    requests: list[Request] = []
    compacts: list[Compact] = []
    for path in args.claude_root.rglob("*.jsonl"):
        if args.project_filter and args.project_filter.lower() not in str(path).lower():
            continue
        r, c = parse_claude_file(path)
        requests.extend(r); compacts.extend(c)
    for path in args.codex_root.rglob("*.jsonl"):
        r, c = parse_codex_file(path)
        requests.extend(r); compacts.extend(c)
    requests.sort(key=lambda r: (r.source, r.session, parse_ts(r.timestamp)))
    compacts.sort(key=lambda e: parse_ts(e.timestamp))
    enrich_compacts(requests, compacts, prices)

    # Absolute source paths are intentionally removed from exported artifacts.
    request_rows = []
    for r in requests:
        row = asdict(r); row.pop("path", None); request_rows.append(row)
    compact_rows = []
    for e in compacts:
        row = asdict(e); row.pop("path", None); compact_rows.append(row)
    thresholds = [int(x) for x in args.thresholds.split(",")]
    observed_posts = [e.post_tokens for e in compacts if e.post_tokens > 0]
    reset_tokens = round(median(observed_posts)) if observed_posts else 70_000
    strategies = strategy_table(requests, thresholds, reset_tokens)
    sessions = session_table(requests, compacts)
    write_csv(args.out / "model_requests.csv", request_rows)
    write_csv(args.out / "compact_events.csv", compact_rows)
    write_csv(args.out / "threshold_strategy.csv", strategies)
    write_csv(args.out / "session_summary.csv", sessions)
    make_charts(args.out, requests, compacts)
    render_report(args.out, requests, compacts, strategies, sessions)
    (args.out / "prices_used.json").write_text(json.dumps(prices, indent=2), encoding="utf-8")
    print(f"wrote {len(requests)} requests and {len(compacts)} compact events to {args.out}")


if __name__ == "__main__":
    main()
