# Scans Claude Code transcripts for per-session activity, skill / slash-command usage and hook cost.
# Usage: uv run python transcript_scan.py <~/.claude/projects dir> <out dir>
# Outputs: <out>/<host>-sessions.csv, <out>/<host>-skills.csv, <out>/<host>-summary.md
import csv
import json
import re
import socket
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PROMPT_GAP_CAP_MIN = 30
BUSY_GAP_CAP_MIN = 5
COMMAND_RE = re.compile(r"<command-name>/?([^<\s]+)</command-name>")


def parse_ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def capped_sum(times, cap_min):
    times = sorted(t for t in times if t)
    return sum(min((b - a).total_seconds() / 60, cap_min) for a, b in zip(times, times[1:]))


def human_prompt_text(rec):
    if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain"):
        return None
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    if any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
        return None
    texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
    return "\n".join(texts) if texts else None


class Stats:
    def __init__(self):
        self.skills = Counter()
        self.skill_sessions = defaultdict(set)
        self.commands = Counter()
        self.hook_ms = defaultdict(list)


def scan_file(path: Path, session_id: str, stats: Stats, is_main: bool):
    prompts, events, tools = [], [], Counter()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"timestamp"' not in line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = parse_ts(rec.get("timestamp"))
            events.append(ts)
            att = rec.get("attachment")
            if isinstance(att, dict) and att.get("command") and att.get("durationMs") is not None:
                stats.hook_ms[(att.get("hookEvent", "?"), att["command"][:90])].append(att["durationMs"])
            if rec.get("subtype") == "stop_hook_summary":
                for info in rec.get("hookInfos") or []:
                    stats.hook_ms[("Stop", str(info.get("command", ""))[:90])].append(info.get("durationMs") or 0)
            msg = rec.get("message") or {}
            if rec.get("type") == "assistant" and isinstance(msg.get("content"), list):
                for c in msg["content"]:
                    if not (isinstance(c, dict) and c.get("type") == "tool_use"):
                        continue
                    tools[c.get("name", "?")] += 1
                    if c.get("name") == "Skill":
                        skill = str((c.get("input") or {}).get("skill", "?"))
                        stats.skills[skill] += 1
                        stats.skill_sessions[skill].add(session_id)
            if not is_main:
                continue
            text = human_prompt_text(rec)
            if text is None:
                continue
            for cmd in COMMAND_RE.findall(text):
                stats.commands[cmd] += 1
            if text.startswith("<local-command") or text.startswith("Caveat:") or "<command-name>" in text:
                continue
            prompts.append(ts)
    return prompts, events, tools


def main():
    root, out_dir = Path(sys.argv[1]).expanduser(), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname()
    stats = Stats()
    rows = []
    for proj in sorted(p for p in root.iterdir() if p.is_dir()):
        for f in proj.glob("*.jsonl"):
            prompts, events, tools = scan_file(f, f.stem, stats, is_main=True)
            evs = [e for e in events if e]
            if not evs:
                continue
            rows.append({
                "host": host, "session_id": f.stem, "project": proj.name,
                "start": min(evs).isoformat()[:16],
                "prompts": len(prompts),
                "engaged_min": round(capped_sum(prompts, PROMPT_GAP_CAP_MIN), 1),
                "busy_min": round(capped_sum(evs, BUSY_GAP_CAP_MIN), 1),
                "tool_calls": sum(tools.values()),
            })
        for sub in proj.glob("*/subagents/*.jsonl"):
            scan_file(sub, sub.parent.parent.name, stats, is_main=False)
    if not rows:
        sys.exit(f"no transcripts found under {root}")

    rows.sort(key=lambda r: r["start"])
    with open(out_dir / f"{host}-sessions.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # One row per skill or typed command, so several hosts' files can be concatenated and summed.
    with open(out_dir / f"{host}-skills.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["host", "kind", "name", "calls", "sessions"])
        for skill, n in stats.skills.most_common():
            w.writerow([host, "skill", skill, n, len(stats.skill_sessions[skill])])
        for cmd, n in stats.commands.most_common():
            w.writerow([host, "command", cmd, n, ""])

    lines = [f"# Transcript summary: {host} ({len(rows)} main sessions, {rows[0]['start']} .. {rows[-1]['start']})", "",
             "## Skill tool invocations (main + subagent transcripts)", "| skill | calls | sessions |", "|---|---|---|"]
    lines += [f"| {s} | {n} | {len(stats.skill_sessions[s])} |" for s, n in stats.skills.most_common()]
    lines += ["", "## Slash commands typed by the user", "| command | count |", "|---|---|"]
    lines += [f"| {c} | {n} |" for c, n in stats.commands.most_common()]
    lines += ["", "## Hook cost", "| event | command | runs | total min | median ms | p90 ms |", "|---|---|---|---|---|---|"]
    for (event, cmd), ms in sorted(stats.hook_ms.items(), key=lambda kv: -sum(kv[1])):
        ms_sorted = sorted(ms)
        p90 = ms_sorted[int(0.9 * (len(ms_sorted) - 1))]
        lines.append(f"| {event} | `{cmd}` | {len(ms)} | {sum(ms)/60000:.1f} | {statistics.median(ms):.0f} | {p90:.0f} |")
    (out_dir / f"{host}-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {host}-sessions.csv, {host}-skills.csv, {host}-summary.md to {out_dir}")


if __name__ == "__main__":
    main()
