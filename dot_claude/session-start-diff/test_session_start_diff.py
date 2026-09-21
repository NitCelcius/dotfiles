"""Drive session_start_diff.py against a throwaway repo and a linked worktree.

Run: uv run --with pytest pytest dot_claude/session-start-diff

Covers each row of the hook's behaviour: silent outside a repo and on a clean tree,
topic check on any diff in the main checkout, no topic check in a worktree, and the
commit ask at the line threshold in both.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent / "session_start_diff.py"
TOPIC_MARK = "same topic"
COMMIT_MARK = "whether to commit"
COMMIT_ASK_LINES = 300


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


@pytest.fixture
def main_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "main"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "commit", "-q", "--allow-empty", "--no-gpg-sign", "-m", "init")
    return repo


@pytest.fixture
def worktree(main_repo: Path, tmp_path: Path) -> Path:
    path = tmp_path / "wt"
    git(main_repo, "worktree", "add", "-q", str(path), "-b", "topic")
    return path


def test_outside_a_repo_is_silent(tmp_path: Path) -> None:
    assert fire(tmp_path) == ""


def test_clean_tree_is_silent(main_repo: Path) -> None:
    assert fire(main_repo) == ""


def test_main_checkout_one_line_asks_for_the_topic_check_only(main_repo: Path) -> None:
    stage_lines(main_repo, "a b.txt", 1)
    out = fire(main_repo)
    assert TOPIC_MARK in out, out
    assert COMMIT_MARK not in out, out


def test_file_name_with_a_space_stays_whole(main_repo: Path) -> None:
    stage_lines(main_repo, "a b.txt", 1)
    out = fire(main_repo)
    assert "a b.txt" in out, out


def test_main_checkout_at_the_threshold_asks_for_topic_and_commit(main_repo: Path) -> None:
    stage_lines(main_repo, "a b.txt", COMMIT_ASK_LINES)
    out = fire(main_repo)
    assert TOPIC_MARK in out, out
    assert COMMIT_MARK in out, out


def test_worktree_one_line_is_silent(worktree: Path) -> None:
    stage_lines(worktree, "c.txt", 1)
    assert fire(worktree) == ""


def test_worktree_at_the_threshold_asks_for_commit_without_topic_check(worktree: Path) -> None:
    stage_lines(worktree, "c.txt", COMMIT_ASK_LINES)
    out = fire(worktree)
    assert TOPIC_MARK not in out, out
    assert COMMIT_MARK in out, out
