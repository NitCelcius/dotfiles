#!/usr/bin/env python3
"""Collect Claude Code compactions and produce privacy-safe feedback.

The PostCompact hook appends compact metadata to a local journal. Reports read
Claude transcripts in place, but never print transcript text or absolute paths.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import compact_analysis
except ModuleNotFoundError:
    # Source-tree layout: this file lives one directory below the analyzer.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import compact_analysis


DATA_ROOT = Path(os.environ.get("CLAUDE_FEEDBACK_DATA_ROOT", Path.home() / ".claude" / "feedback-on-compaction"))
JOURNAL = DATA_ROOT / "compactions.jsonl"
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"


def normalized(path: str | Path) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(str(path))))


def is_within(path: str | Path, root: str | Path) -> bool:
    candidate = normalized(path)
    scope = normalized(root)
    try:
        return os.path.commonpath([candidate, scope]) == scope
    except ValueError:
        return False


def read_journal() -> list[dict[str, Any]]:
    if not JOURNAL.exists():
        return []
    rows: list[dict[str, Any]] = []
    with JOURNAL.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def collect() -> int:
    """Record one PostCompact payload without ever blocking Claude Code."""
    try:
        payload = json.load(sys.stdin)
        summary = payload.get("compact_summary", "")
        record = {
            "schema_version": 1,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "session_id": str(payload.get("session_id") or ""),
            "transcript_path": str(payload.get("transcript_path") or ""),
            "cwd": str(payload.get("cwd") or ""),
            "trigger": str(payload.get("trigger") or "unknown"),
            "compact_summary": summary if isinstance(summary, str) else json.dumps(summary, ensure_ascii=False),
        }
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        with JOURNAL.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # A telemetry hook must not interrupt the session.
        print(f"feedback-on-compaction collector skipped: {exc}", file=sys.stderr)
    return 0


def transcript_cwd(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cwd = row.get("cwd")
                if cwd:
                    return str(cwd)
    except OSError:
        return ""
    return ""


def transcript_paths(scope: str, cwd: Path, journal: list[dict[str, Any]]) -> list[Path]:
    if scope == "all":
        return sorted(CLAUDE_PROJECTS.rglob("*.jsonl"))

    selected: set[Path] = set()
    for row in journal:
        row_cwd = str(row.get("cwd") or "")
        transcript = Path(str(row.get("transcript_path") or ""))
        if row_cwd and is_within(row_cwd, cwd) and transcript.is_file():
            selected.add(transcript)

    # This also discovers compactions from before the hook was installed.
    for path in CLAUDE_PROJECTS.rglob("*.jsonl"):
        row_cwd = transcript_cwd(path)
        if row_cwd and is_within(row_cwd, cwd):
            selected.add(path)
    return sorted(selected)


def finite(values: Iterable[float]) -> list[float]:
    return [value for value in values if math.isfinite(value)]


def med(values: Iterable[float]) -> float:
    items = list(values)
    return statistics.median(items) if items else 0.0


def token_count(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return f"{value:.0f}"


def captured_count(journal: list[dict[str, Any]], scope: str, cwd: Path) -> int:
    if scope == "all":
        return len(journal)
    return sum(1 for row in journal if row.get("cwd") and is_within(str(row["cwd"]), cwd))


def recommendation(events: list[compact_analysis.Compact]) -> str:
    measured = [event for event in events if event.requests_observed > 0 and math.isfinite(event.break_even_requests)]
    if not measured:
        return "Not enough post-compaction requests have been observed to recommend a policy yet."
    required = max(1, math.ceil(med(event.break_even_requests for event in measured)))
    paid = sum(event.requests_observed >= event.break_even_requests for event in measured)
    rate = paid / len(measured)
    if rate < 0.5:
        return (
            f"Delay optional/manual compaction unless you expect at least {required} more substantial "
            "requests; most observed compactions did not recover their estimated overhead."
        )
    return (
        f"Your observed compactions generally paid back. Keep compacting when you expect at least "
        f"{required} more substantial requests in the session."
    )


def report(scope: str, cwd: Path) -> int:
    journal = read_journal()
    paths = transcript_paths(scope, cwd, journal)
    requests: list[compact_analysis.Request] = []
    events: list[compact_analysis.Compact] = []
    unreadable = 0
    for path in paths:
        try:
            parsed_requests, parsed_events = compact_analysis.parse_claude_file(path)
        except (OSError, ValueError, TypeError):
            unreadable += 1
            continue
        requests.extend(parsed_requests)
        events.extend(parsed_events)

    requests.sort(key=lambda row: (row.session, compact_analysis.parse_ts(row.timestamp)))
    events.sort(key=lambda row: compact_analysis.parse_ts(row.timestamp))
    compact_analysis.enrich_compacts(requests, events, compact_analysis.DEFAULT_PRICES)

    measured = [event for event in events if event.requests_observed > 0 and math.isfinite(event.break_even_requests)]
    paid = [event for event in measured if event.requests_observed >= event.break_even_requests]
    no_followup = [event for event in events if event.requests_observed == 0]
    break_evens = finite(event.break_even_requests for event in measured)
    savings = [max(0, event.pre_tokens - event.post_tokens) for event in measured]
    title_scope = "all Claude Code projects" if scope == "all" else "this repository"

    print("# Compaction feedback")
    print()
    print(f"Scope: {title_scope}")
    print(f"Analyzed: {len(paths)} transcripts, {len(events)} compactions, {len(requests)} model requests")
    print(f"Captured by the new hook: {captured_count(journal, scope, cwd)} compactions")
    if unreadable:
        print(f"Unreadable transcripts skipped: {unreadable}")
    print()
    print("## Recommendation")
    print()
    print(recommendation(events))
    print()
    print("## Evidence")
    print()
    if not events:
        print("No compaction events were found for this scope.")
        return 0
    rate = (len(paid) / len(measured) * 100) if measured else 0.0
    print(f"- Estimated overhead recovered: {len(paid)}/{len(measured)} measurable events ({rate:.0f}%)")
    print(f"- No post-compaction request available yet: {len(no_followup)} events")
    print(f"- Median pre/post context: {token_count(med(e.pre_tokens for e in measured))} / {token_count(med(e.post_tokens for e in measured))} tokens")
    print(f"- Median context removed: {token_count(med(savings))} tokens")
    print(f"- Median estimated break-even: {med(break_evens):.1f} subsequent requests")
    print(f"- Median observed requests after compaction: {med(e.requests_observed for e in measured):.1f}")
    print()
    print("## Recent events")
    print()
    print("| Date | Trigger | Pre → post | Later requests | Break-even | Outcome |")
    print("|---|---|---:|---:|---:|---|")
    for event in reversed(events[-10:]):
        date = event.timestamp[:10] or "unknown"
        before_after = f"{token_count(event.pre_tokens)} → {token_count(event.post_tokens)}"
        if event.requests_observed == 0 or not math.isfinite(event.break_even_requests):
            break_even = "—"
            outcome = "not yet measurable"
        else:
            break_even = f"{event.break_even_requests:.1f}"
            outcome = "recovered" if event.requests_observed >= event.break_even_requests else "not recovered"
        print(f"| {date} | {event.trigger} | {before_after} | {event.requests_observed} | {break_even} | {outcome} |")
    print()
    print("## Interpretation limits")
    print()
    print("Break-even uses API-equivalent prices and estimated summary size; it is not subscription quota accounting. ")
    print("The report reads local transcripts only for token/structural metadata and emits no transcript text, compact summaries, tool arguments, or absolute paths.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("collect", help="read one PostCompact hook payload from stdin")
    report_parser = subparsers.add_parser("report", help="analyze recorded Claude Code compactions")
    report_parser.add_argument("--scope", choices=("repo", "all"), required=True)
    report_parser.add_argument("--cwd", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if args.command == "collect":
        return collect()
    return report(args.scope, args.cwd.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
