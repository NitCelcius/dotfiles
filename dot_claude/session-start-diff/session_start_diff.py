#!/usr/bin/env python3
"""Tell Claude to offer a commit when a session starts on a large pending diff.

Wired as a SessionStart hook. Reads the hook payload on stdin for `cwd`, runs
`git diff HEAD --shortstat` there, and when insertions + deletions reach
PENDING_LINES_THRESHOLD prints `additionalContext` asking Claude to check with the
user before doing anything else. Prints nothing otherwise, including outside a git
repo or in a repo with no commits yet.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

PENDING_LINES_THRESHOLD = 300
GIT_TIMEOUT_SECONDS = 10
CHANGED_LINES = re.compile(r"(\d+) (?:insertion|deletion)")


def pending_lines(cwd: str) -> int | None:
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--shortstat"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return sum(int(n) for n in CHANGED_LINES.findall(result.stdout))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    cwd = payload.get("cwd") or "."

    lines = pending_lines(cwd)
    if lines is None or lines < PENDING_LINES_THRESHOLD:
        return 0

    context = (
        f"The working tree has {lines} uncommitted changed lines "
        f"(git diff HEAD). Before starting on the user's request, ask whether "
        f"they want to commit first."
    )
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
