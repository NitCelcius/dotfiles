#!/usr/bin/env python3
"""Prompt Claude to log the why of each dotfiles commit to the Notion change log.

It tells Claude, which drafts the row per step of the `modifying-dotfiles` skill and writes it after the user approves. The dotfiles repo is found with `chezmoi source-path`

Subcommands:

  post-commit    PostToolUse hook (matcher `Bash|PowerShell`). After a command that
                 runs `git ... commit`, looks for a branch tip in the dotfiles repo
                 committed in the last RECENT_SECONDS and not yet prompted for. Judging
                 by the repo, not the tool response, also covers `cd`, `git -C` and
                 worktrees, and stays silent when the commit failed.
  session-start  SessionStart hook. Counts commits on local and remote-tracking
                 branches authored after the last logged commit and reports them in one
                 line. The first run only records a baseline: older commits stay
                 unlogged on purpose.
  mark <rev>     Run by Claude after writing (or deliberately skipping) a row. Moves
                 the baseline to that commit's author time.

The baseline is an author time, not a SHA, because PRs land by rebase and rewrite
SHAs while keeping author dates. A commit authored before the baseline on a parallel
branch is therefore missed.

State lives in STATE_PATH (override with DOTFILES_CHANGE_LOG_STATE); the repo can be
overridden with DOTFILES_CHANGE_LOG_REPO. Any failure prints nothing and exits 0.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

STATE_PATH = Path.home() / ".local" / "state" / "dotfiles-change-log.json"
RECENT_SECONDS = 120
MAX_PROMPTED = 50
GIT_TIMEOUT_SECONDS = 10
# `git commit`, `git -C path commit`, `git -c k=v commit`; not `git commit-tree`.
GIT_COMMIT = re.compile(r"\bgit(?:\s+-[Cc]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+commit(?![\w-])")


def run(args: list[str], cwd: str | None = None) -> str | None:
    try:
        result = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def dotfiles_repo() -> str | None:
    override = os.environ.get("DOTFILES_CHANGE_LOG_REPO")
    if override:
        return override
    path = run(["chezmoi", "source-path"])
    return path.strip() if path else None


def state_path() -> Path:
    override = os.environ.get("DOTFILES_CHANGE_LOG_STATE")
    return Path(override) if override else STATE_PATH


def load_state() -> dict | None:
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_state(state: dict) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def emit(event: str, context: str) -> None:
    output = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context}}
    print(json.dumps(output))


def post_commit(payload: dict) -> None:
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not GIT_COMMIT.search(command):
        return
    repo = dotfiles_repo()
    if repo is None:
        return
    tips = run(
        ["git", "for-each-ref", "refs/heads",
         "--format=%(objectname) %(committerdate:unix) %(refname:short)"],
        cwd=repo,
    )
    if not tips:
        return

    state = load_state() or {}
    prompted = state.get("prompted", [])
    now = time.time()
    fresh = []
    for line in tips.splitlines():
        sha, committed, branch = line.split(" ", 2)
        if now - int(committed) > RECENT_SECONDS or sha in prompted or sha in fresh:
            continue
        fresh.append(sha)
        prompted.append(sha)
        landed = f"{sha} on `{branch}`"
    if not fresh:
        return

    state["prompted"] = prompted[-MAX_PROMPTED:]
    save_state(state)
    rev = fresh[0]
    if len(fresh) > 1:
        landed = ", ".join(fresh)
        rev = "<sha>"
    script = Path(__file__).resolve()
    emit(
        "PostToolUse",
        f"A dotfiles commit just landed: {landed}. Follow step 5 of the "
        "`modifying-dotfiles` skill: draft its 設定変更ログ row, show it to the user, "
        "and write it only after approval. After writing the row, or if the user "
        f'skips it, run `python "{script}" mark {rev}`.',
    )


def session_start() -> None:
    repo = dotfiles_repo()
    if repo is None:
        return
    log = run(["git", "log", "--branches", "--remotes", "--no-merges", "--format=%at %s"], cwd=repo)
    if log is None:
        return
    commits = {line for line in log.splitlines() if line}  # a rebased copy shares %at and %s
    newest = max((int(line.split(" ", 1)[0]) for line in commits), default=0)

    state = load_state()
    if state is None or "baseline" not in state:
        save_state({**(state or {}), "baseline": newest})
        return
    unlogged = [line for line in commits if int(line.split(" ", 1)[0]) > state["baseline"]]
    if not unlogged:
        return
    emit(
        "SessionStart",
        f"{len(unlogged)} dotfiles commit(s) have no 設定変更ログ row yet; run the "
        "Reconcile mode of the `modifying-dotfiles` skill when the user's work allows.",
    )


def mark(rev: str) -> int:
    repo = dotfiles_repo()
    if repo is None:
        print("dotfiles repo not found", file=sys.stderr)
        return 1
    authored = run(["git", "log", "-1", "--format=%at", rev], cwd=repo)
    if not authored:
        print(f"unknown commit: {rev}", file=sys.stderr)
        return 1
    state = load_state() or {}
    state["baseline"] = max(state.get("baseline", 0), int(authored))
    save_state(state)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "mark":
        return mark(argv[2])
    if len(argv) != 2 or argv[1] not in ("post-commit", "session-start"):
        print("usage: dotfiles_change_log.py post-commit | session-start | mark <rev>", file=sys.stderr)
        return 2
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    try:
        if argv[1] == "post-commit":
            post_commit(payload)
        else:
            session_start()
    except (OSError, ValueError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
