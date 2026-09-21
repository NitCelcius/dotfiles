"""Drive session_start_diff.py against a throwaway repo and a linked worktree.

Run: python test_session_start_diff.py

Covers each row of the hook's behaviour: silent outside a repo and on a clean tree,
topic check on any diff in the main checkout, no topic check in a worktree, and the
commit ask at the line threshold in both.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "session_start_diff.py"
TOPIC_MARK = "same topic"
COMMIT_MARK = "whether to commit"

failures: list[str] = []
passed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
        return
    failures.append(f"{name}: {detail}")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def fire(cwd: Path) -> str:
    done = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"cwd": str(cwd)}),
        capture_output=True,
        text=True,
        check=True,
    )
    if not done.stdout.strip():
        return ""
    return json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"]


def stage_lines(repo: Path, name: str, count: int) -> None:
    (repo / name).write_text("x\n" * count, encoding="utf-8")
    git(repo, "add", name)


def main() -> int:
    root = Path(tempfile.mkdtemp())
    try:
        main_repo = root / "main"
        worktree = root / "wt"
        main_repo.mkdir()

        check("outside a repo is silent", fire(main_repo) == "")

        git(main_repo, "init", "-q")
        git(main_repo, "commit", "-q", "--allow-empty", "--no-gpg-sign", "-m", "init")
        git(main_repo, "worktree", "add", "-q", str(worktree), "-b", "topic")
        check("clean tree is silent", fire(main_repo) == "")

        stage_lines(main_repo, "a b.txt", 1)
        out = fire(main_repo)
        check("main 1 line: topic check", TOPIC_MARK in out, out)
        check("main 1 line: no commit ask", COMMIT_MARK not in out, out)
        check("file name with a space stays whole", "a b.txt" in out, out)

        stage_lines(main_repo, "a b.txt", 300)
        out = fire(main_repo)
        check("main 300 lines: topic check", TOPIC_MARK in out, out)
        check("main 300 lines: commit ask", COMMIT_MARK in out, out)

        stage_lines(worktree, "c.txt", 1)
        check("worktree 1 line is silent", fire(worktree) == "")

        stage_lines(worktree, "c.txt", 300)
        out = fire(worktree)
        check("worktree 300 lines: no topic check", TOPIC_MARK not in out, out)
        check("worktree 300 lines: commit ask", COMMIT_MARK in out, out)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    total = passed + len(failures)
    for failure in failures:
        print(f"FAIL {failure}")
    print(f"{passed}/{total} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
