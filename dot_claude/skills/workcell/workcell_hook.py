#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = "workcell/event@1"


def root_dir() -> Path:
    value = os.environ.get("WORKCELL_ROOT")
    return Path(value).expanduser().resolve() if value else (Path.home() / ".local" / "share" / "workcell").resolve()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def safe_id(value: Any, fallback: str) -> str:
    text = str(value or fallback)
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in text)


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
    lock = path.with_suffix(path.suffix + ".lock")
    acquired = False
    deadline = time.monotonic() + 0.35
    while time.monotonic() < deadline:
        try:
            lock.mkdir()
            acquired = True
            break
        except FileExistsError:
            time.sleep(0.01)
    if not acquired:
        # Telemetry must never block Claude Code. Drop the index event rather than failing the hook.
        return
    try:
        with path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(line)
            fh.flush()
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


def sync_transcript(source_raw: Any, destination: Path) -> None:
    if not source_raw:
        return
    source = Path(str(source_raw)).expanduser()
    if not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Claude transcripts are normally append-only. Append the delta when possible.
    # If the source shrinks (e.g. implementation changes or replacement), replace the archive.
    src_size = source.stat().st_size
    if not destination.exists():
        shutil.copy2(source, destination)
        return
    dst_size = destination.stat().st_size
    if src_size == dst_size:
        return
    if src_size > dst_size:
        with source.open("rb") as src, destination.open("ab") as dst:
            src.seek(dst_size)
            shutil.copyfileobj(src, dst, length=1024 * 1024)
        return
    shutil.copy2(source, destination)


def skill_name(payload: dict[str, Any]) -> str | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    for key in ("skill", "name", "command", "skill_name"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value.lstrip("/")
    return None


def event_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    event = payload.get("hook_event_name")
    base: dict[str, Any] = {
        "schema": SCHEMA,
        "timestamp": now_iso(),
        "event": None,
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
    }
    if payload.get("agent_id"):
        base["agent_id"] = payload.get("agent_id")
    if payload.get("agent_type"):
        base["agent_type"] = payload.get("agent_type")

    if event == "SessionStart":
        base["event"] = "session_started"
        base["source"] = payload.get("source")
        base["model"] = payload.get("model")
    elif event == "SessionEnd":
        base["event"] = "session_ended"
        base["reason"] = payload.get("reason")
    elif event == "UserPromptExpansion":
        base["event"] = "command_invoked"
        base["command_name"] = payload.get("command_name")
        base["command_source"] = payload.get("command_source")
        base["expansion_type"] = payload.get("expansion_type")
    elif event == "PreToolUse" and payload.get("tool_name") == "Skill":
        base["event"] = "skill_invoked"
        base["skill"] = skill_name(payload)
    elif event == "SubagentStart":
        base["event"] = "subagent_started"
        base["workcell_agent"] = str(payload.get("agent_type", "")).startswith("team-")
    elif event == "SubagentStop":
        base["event"] = "subagent_stopped"
        base["workcell_agent"] = str(payload.get("agent_type", "")).startswith("team-")
    elif event == "PostModelSwitch":
        base["event"] = "model_switched"
        # Field names have evolved; preserve whichever common variants are present.
        for key in ("model", "new_model", "from_model", "to_model", "source"):
            if key in payload:
                base[key] = payload[key]
    elif event == "WorktreeRemove":
        base["event"] = "worktree_removed"
        base["worktree_path"] = payload.get("worktree_path")
    else:
        return None
    return base


def archive_for_event(payload: dict[str, Any], root: Path) -> None:
    event = payload.get("hook_event_name")
    session_id = safe_id(payload.get("session_id"), "unknown-session")
    transcript_root = root / "telemetry" / "transcripts" / session_id

    if event in {"Stop", "SessionEnd"}:
        sync_transcript(payload.get("transcript_path"), transcript_root / "main.jsonl")
    elif event == "SubagentStop":
        agent_id = safe_id(payload.get("agent_id"), "unknown-agent")
        source = payload.get("agent_transcript_path")
        sync_transcript(source, transcript_root / "subagents" / f"{agent_id}.jsonl")
        # Also keep the parent transcript reasonably current without requiring a separate turn end.
        sync_transcript(payload.get("transcript_path"), transcript_root / "main.jsonl")


def plugin_root() -> Path:
    value = os.environ.get("CLAUDE_PLUGIN_ROOT")
    return Path(value).resolve() if value else Path(__file__).resolve().parent


def announce_session_start(root: Path) -> None:
    """Tell the session where records live and how to reach the CLI.

    Only hooks are given CLAUDE_PLUGIN_ROOT, so without this the agent cannot
    locate the CLI unless a shim happens to be on PATH.
    """
    cli = plugin_root() / "workcell.py"
    context = "\n".join([
        f"Workcell records: {root}",
        f'Workcell CLI: python "{cli}" (or `workcell` when a shim is on PATH)',
    ])
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": context,
    }}, ensure_ascii=False))


def handle(payload: dict[str, Any]) -> None:
    root = root_dir()
    archive_for_event(payload, root)
    record = event_record(payload)
    if record is not None:
        append_jsonl(root / "telemetry" / "events.jsonl", record)
    if payload.get("hook_event_name") == "SessionStart":
        announce_session_start(root)


def main() -> int:
    # Telemetry must fail open: never stop Claude Code because logging failed.
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return 0
        payload = json.loads(raw)
        if isinstance(payload, dict):
            handle(payload)
    except Exception as exc:  # noqa: BLE001 - hook intentionally fails open
        try:
            print(f"workcell_hook: {exc}", file=sys.stderr)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
