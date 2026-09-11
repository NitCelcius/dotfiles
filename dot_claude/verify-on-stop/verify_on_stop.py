#!/usr/bin/env python3
"""Run a project's quick verification when Claude tries to finish a turn.

Wired as a Stop hook. It reads the `quick` command out of the project CLAUDE.md's
`## Verification` block, runs it, and exits 2 on failure so Claude sees the output
and cannot close the task on a claim alone.

It stays out of the way by design, exiting 0 without running anything when:

  - the project has no CLAUDE.md, or no `## Verification` block in it
  - `quick` is recorded as absent ("none (not yet set up)")
  - the project is not a git repo, so there is no cheap way to tell what changed
  - nothing has changed since the last run that passed
  - it already blocked once on this exact working-tree state

The command is run through the platform shell, so write `quick` to work in both
sh and cmd.exe. Chaining with `&&` is safe; shell-specific syntax is not.

`--selftest` runs the parser fixtures and prints a pass/fail line per case. It
takes no stdin and touches nothing on disk.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_ROOT = Path(
    os.environ.get("CLAUDE_VERIFY_DATA_ROOT", Path.home() / ".claude" / "verify-on-stop")
)
STATE_FILE = DATA_ROOT / "state.json"
# A hook nobody wired up is indistinguishable from one that passes, so every
# invocation leaves a line here saying what it decided and why.
LOG_FILE = DATA_ROOT / "invocations.jsonl"
LOG_KEEP_LINES = 200

TIMEOUT_SECONDS = int(os.environ.get("CLAUDE_VERIFY_TIMEOUT", "180"))
MAX_OUTPUT_LINES = 40
MAX_FINGERPRINT_BYTES = 4 * 1024 * 1024

HEADING = re.compile(r"^##\s+Verification\s*$")
NEXT_HEADING = re.compile(r"^##\s+\S")
QUICK_BULLET = re.compile(r"^\s*[-*]\s+\*\*quick\*\*", re.IGNORECASE)
BACKTICK_SPAN = re.compile(r"`([^`]+)`")

# Exit codes the Stop hook contract reads.
EXIT_ALLOW_STOP = 0
EXIT_BLOCK_STOP = 2


def parse_quick_command(text: str) -> str | None:
    """Return the `quick` command from a `## Verification` block, or None.

    None means "do not run anything" for every reason: no block, no quick bullet,
    quick recorded as absent, or a line whose command is ambiguous. A hook that
    guesses here would run the wrong command on every turn, so anything but one
    unmistakable backtick span is treated as absent.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if HEADING.match(line)), None)
    if start is None:
        return None

    for line in lines[start + 1 :]:
        if NEXT_HEADING.match(line):
            return None
        if not QUICK_BULLET.match(line):
            continue
        spans = BACKTICK_SPAN.findall(line)
        if len(spans) != 1:
            return None
        command = spans[0].strip()
        return command or None
    return None


def find_claude_md(cwd: Path, ceiling: Path) -> Path | None:
    """Walk up from cwd to ceiling inclusive, returning the first CLAUDE.md."""
    for directory in [cwd, *cwd.parents]:
        candidate = directory / "CLAUDE.md"
        if candidate.is_file():
            return candidate
        if directory == ceiling:
            break
    return None


def git(args: list[str], cwd: Path) -> str | None:
    try:
        done = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def untracked_paths(status_z: str) -> list[str]:
    """Untracked paths from `git status --porcelain=v1 -z` output.

    The -z form is what makes this safe: porcelain v1 quotes and escapes paths
    containing spaces or non-ASCII, and these trees are full of Japanese names.
    """
    return sorted(
        entry[3:] for entry in status_z.split("\0") if entry.startswith("?? ")
    )


def working_tree_fingerprint(root: Path) -> str | None:
    """Hash HEAD, the uncommitted patch, and untracked file contents.

    `git diff HEAD` covers tracked files and `git status` names untracked ones,
    but neither reflects an *edit to an untracked file* — the case where Claude
    writes a new module and keeps revising it. Without hashing those contents the
    guard would skip verification for the whole life of a new file.
    """
    head = git(["rev-parse", "HEAD"], root) or ""
    status = git(["status", "--porcelain=v1", "-uall", "-z"], root)
    if status is None:
        return None
    patch = git(["diff", "HEAD"], root) or ""

    digest = hashlib.sha256()
    budget = MAX_FINGERPRINT_BYTES
    for part in (head, status, patch):
        blob = part.encode("utf-8", "replace")
        budget -= len(blob)
        if budget < 0:
            return None  # Too big to fingerprint cheaply; treat as always changed.
        digest.update(blob)
        digest.update(b"\0")

    for relative in untracked_paths(status):
        target = root / relative
        try:
            if not target.is_file():
                continue
            blob = target.read_bytes()
        except OSError:
            return None
        budget -= len(blob)
        if budget < 0:
            return None
        digest.update(relative.encode("utf-8", "replace"))
        digest.update(blob)
        digest.update(b"\0")
    return digest.hexdigest()


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    try:
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    except OSError:
        pass  # A hook that cannot cache must still not break the session.


def log_decision(reason: str, **fields: object) -> None:
    """Append one line recording what this invocation decided."""
    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reason": reason}
    entry.update(fields)
    try:
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        previous = (
            LOG_FILE.read_text(encoding="utf-8").splitlines()[-(LOG_KEEP_LINES - 1) :]
            if LOG_FILE.exists()
            else []
        )
        LOG_FILE.write_text(
            "\n".join([*previous, json.dumps(entry, ensure_ascii=False)]) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError):
        pass  # Logging must never be the thing that breaks a turn.


def tail(text: str, limit: int = MAX_OUTPUT_LINES) -> str:
    lines = text.rstrip().splitlines()
    if len(lines) <= limit:
        return "\n".join(lines)
    return "\n".join(["... (earlier output trimmed)", *lines[-limit:]])


def run() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        log_decision("unreadable-stdin")
        return EXIT_ALLOW_STOP

    cwd_text = str(payload.get("cwd") or os.getcwd())

    # Claude is already responding to a block from this hook; never block twice.
    if payload.get("stop_hook_active"):
        log_decision("stop-hook-active", cwd=cwd_text)
        return EXIT_ALLOW_STOP

    cwd = Path(cwd_text).resolve()
    toplevel = git(["rev-parse", "--show-toplevel"], cwd)
    if not toplevel:
        log_decision("not-a-git-repo", cwd=cwd_text)
        return EXIT_ALLOW_STOP
    root = Path(toplevel.strip()).resolve()

    claude_md = find_claude_md(cwd, root)
    if claude_md is None:
        log_decision("no-claude-md", cwd=cwd_text)
        return EXIT_ALLOW_STOP

    try:
        command = parse_quick_command(claude_md.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        log_decision("claude-md-unreadable", cwd=cwd_text)
        return EXIT_ALLOW_STOP
    if command is None:
        log_decision("no-quick-command", cwd=cwd_text)
        return EXIT_ALLOW_STOP

    key = os.path.normcase(str(root))
    state = load_state()
    entry = state.get(key, {})
    fingerprint = working_tree_fingerprint(root)

    if fingerprint is not None:
        if fingerprint in entry.get("passed", []):
            log_decision("unchanged-since-pass", cwd=cwd_text, command=command)
            return EXIT_ALLOW_STOP
        if entry.get("blocked") == fingerprint:
            # Already reported this exact state once. Blocking again would trap
            # the session on a failure Claude has decided not to fix.
            log_decision("already-blocked-on-this-state", cwd=cwd_text, command=command)
            return EXIT_ALLOW_STOP

    try:
        done = subprocess.run(
            command,
            cwd=root,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(
            f"quick verification timed out after {TIMEOUT_SECONDS}s: {command}\n"
            f"Shorten the quick command in {claude_md.name}'s ## Verification block, "
            f"or move the slow part to full.",
            file=sys.stderr,
        )
        log_decision("timed-out", cwd=cwd_text, command=command, seconds=TIMEOUT_SECONDS)
        return EXIT_BLOCK_STOP
    except OSError as exc:
        print(f"quick verification could not start: {command} ({exc})", file=sys.stderr)
        log_decision("could-not-start", cwd=cwd_text, command=command, error=str(exc))
        return EXIT_ALLOW_STOP

    if done.returncode == 0:
        # Record the tree both before and after the run. A quick command that
        # writes anything git can see (a log, a report, an un-ignored cache)
        # would otherwise leave a tree that never matches what was stored, and
        # the guard would re-run it on every single turn.
        after = working_tree_fingerprint(root)
        entry["passed"] = [f for f in (fingerprint, after) if f is not None]
        entry.pop("blocked", None)
        state[key] = entry
        save_state(state)
        log_decision("passed", cwd=cwd_text, command=command)
        return EXIT_ALLOW_STOP

    entry["blocked"] = fingerprint
    entry.pop("passed", None)
    state[key] = entry
    save_state(state)

    print(
        f"quick verification failed (exit {done.returncode}): {command}\n"
        f"This is the project's own ## Verification command. Fix what it reports "
        f"before finishing, or say plainly that you are leaving it failing.\n\n"
        f"{tail((done.stdout or '') + (done.stderr or ''))}",
        file=sys.stderr,
    )
    log_decision("blocked", cwd=cwd_text, command=command, exit_code=done.returncode)
    return EXIT_BLOCK_STOP


SELFTEST_CASES: list[tuple[str, str, str | None]] = [
    (
        "block as welcome-claude emits it",
        "# CLAUDE.md\n\n## Verification\n\n"
        "- **quick** (task close-out, aim for under 30s): `uv run pytest -q`\n"
        "- **full** (before a commit or PR): `uv run pytest`\n"
        "- **Out of scope**: figure generation\n\n## Next Section\n",
        "uv run pytest -q",
    ),
    (
        "quick recorded as absent",
        "## Verification\n\n- **quick**: none (not yet set up)\n- **full**: `npm run build`\n",
        None,
    ),
    ("no Verification block at all", "# CLAUDE.md\n\n## Commands\n\n- `npm test`\n", None),
    (
        "ambiguous line with two spans",
        "## Verification\n\n- **quick**: `npm run lint` then `npm test`\n",
        None,
    ),
    (
        "quick bullet belongs to a later section",
        "## Verification\n\n- **full**: `npm run build`\n\n## Other\n\n- **quick**: `rm -rf /`\n",
        None,
    ),
    (
        "chained command survives intact",
        "## Verification\n\n- **quick** (task close-out): `uv run ruff check . && uv run pytest -q`\n",
        "uv run ruff check . && uv run pytest -q",
    ),
    ("empty span", "## Verification\n\n- **quick**: ``\n", None),
]


UNTRACKED_CASES: list[tuple[str, str, list[str]]] = [
    ("nothing untracked", " M src/app.py\0M  README.md\0", []),
    ("untracked among modified", " M src/app.py\0?? notes.md\0", ["notes.md"]),
    (
        "paths with spaces and Japanese survive -z",
        "?? data/測色 raw.csv\0?? 研究室/メモ.md\0",
        ["data/測色 raw.csv", "研究室/メモ.md"],
    ),
    ("empty output", "", []),
]


def selftest() -> int:
    failures = 0
    total = 0
    for name, text, expected in SELFTEST_CASES:
        actual = parse_quick_command(text)
        ok = actual == expected
        total += 1
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  parse_quick_command: {name}")
        if not ok:
            print(f"      expected {expected!r}, got {actual!r}")
    for name, text, expected_paths in UNTRACKED_CASES:
        actual_paths = untracked_paths(text)
        ok = actual_paths == sorted(expected_paths)
        total += 1
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  untracked_paths: {name}")
        if not ok:
            print(f"      expected {sorted(expected_paths)!r}, got {actual_paths!r}")
    print(f"\n{total - failures}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv[1:] else run())
