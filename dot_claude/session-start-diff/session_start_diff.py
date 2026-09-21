#!/usr/bin/env python3
"""Tell Claude about uncommitted changes when a session starts.

Wired as a SessionStart hook. Reads the hook payload on stdin for `cwd` and runs
`git diff HEAD` there. On any pending change it prints `additionalContext` with the
branch, line count and changed files, asking Claude to check that the user's first
request is on the same topic before building on them. At COMMIT_RECOMMEND_LINES or
more it also asks Claude to recommend a commit. Prints nothing on a clean tree,
outside a git repo, or in a repo with no commits yet.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

COMMIT_RECOMMEND_LINES = 300
MAX_LISTED_FILES = 15
GIT_TIMEOUT_SECONDS = 10
CHANGED_LINES = re.compile(r"(\d+) (?:insertion|deletion)")


def git(cwd: str, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def build_context(cwd: str) -> str | None:
    shortstat = git(cwd, "diff", "HEAD", "--shortstat")
    if not shortstat:
        return None
    lines = sum(int(n) for n in CHANGED_LINES.findall(shortstat))
    files = (git(cwd, "diff", "HEAD", "--name-only") or "").split()
    branch = (git(cwd, "branch", "--show-current") or "").strip() or "(detached HEAD)"

    listed = files[:MAX_LISTED_FILES]
    if len(files) > MAX_LISTED_FILES:
        listed.append(f"... and {len(files) - MAX_LISTED_FILES} more")

    parts = [
        f"Uncommitted changes on branch `{branch}`: {lines} changed lines "
        f"in {len(files)} files (git diff HEAD).",
        "Changed files: " + ", ".join(listed),
        "When the user's first request arrives, judge whether it is on the same topic "
        "as these changes. If it is not clearly the same, ask before building on them, "
        "so work on a different topic does not pile onto an uncommitted diff.",
    ]
    if lines >= COMMIT_RECOMMEND_LINES:
        parts.append(
            f"The diff is {COMMIT_RECOMMEND_LINES}+ lines: recommend committing it "
            "before starting new work."
        )
    return "\n".join(parts)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}

    context = build_context(payload.get("cwd") or ".")
    if context is None:
        return 0

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
