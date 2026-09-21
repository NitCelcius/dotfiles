#!/usr/bin/env python3
"""Tell Claude about uncommitted changes when a session starts.

Wired as a SessionStart hook. Reads the hook payload on stdin for `cwd` and runs
`git diff HEAD` there, then prints `additionalContext` with the branch, line count
and changed files:

  - in the main checkout, any pending change asks Claude to check that the user's
    first request is on the same topic before building on it
  - in a linked worktree that check is skipped, since a worktree holds one topic
  - at COMMIT_ASK_LINES or more, in either, Claude must ask whether to commit
    before starting work

Prints nothing when there is nothing to say, outside a git repo, or in a repo with
no commits yet.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

COMMIT_ASK_LINES = 300
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
    in_worktree = is_linked_worktree(cwd)
    if in_worktree and lines < COMMIT_ASK_LINES:
        return None

    files = (git(cwd, "diff", "HEAD", "--name-only") or "").splitlines()
    branch = (git(cwd, "branch", "--show-current") or "").strip() or "(detached HEAD)"

    listed = files[:MAX_LISTED_FILES]
    if len(files) > MAX_LISTED_FILES:
        listed.append(f"... and {len(files) - MAX_LISTED_FILES} more")

    parts = [
        f"Uncommitted changes on branch `{branch}`: {lines} changed lines "
        f"in {len(files)} files (git diff HEAD).",
        "Changed files: " + ", ".join(listed),
    ]
    if not in_worktree:
        parts.append(
            "When the user's first request arrives, judge whether it is on the same "
            "topic as these changes, from the branch and file names. If that is not "
            "enough to tell, read the diff. If it is a different topic, or still "
            "unclear, ask before building on the changes."
        )
    if lines >= COMMIT_ASK_LINES:
        parts.append(
            f"The diff is {COMMIT_ASK_LINES}+ lines: before starting any work, ask "
            "the user whether to commit it first."
        )
    return "\n".join(parts)


def is_linked_worktree(cwd: str) -> bool:
    git_dir = git(cwd, "rev-parse", "--absolute-git-dir")
    common_dir = git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if git_dir is None or common_dir is None:
        return False
    return os.path.normcase(git_dir.strip()) != os.path.normcase(common_dir.strip())


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
