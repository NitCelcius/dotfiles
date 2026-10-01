"""Drive dotfiles_change_log.py against a throwaway repo standing in for dotfiles.

Run: uv run --with pytest pytest dot_claude/dotfiles-change-log

Covers the post-commit prompt (fires once per new tip, ignores other commands, a
failed commit and old tips, follows worktrees), the session-start baseline and count,
and `mark` moving the baseline.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent / "dotfiles_change_log.py"
STEP_MARK = "step 5"
RECONCILE_MARK = "Reconcile mode"
OLD_DATE = "2020-01-01T00:00:00"


def git(cwd: Path, *args: str, date: str | None = None) -> str:
    env = dict(os.environ)
    if date:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = date
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd, check=True, capture_output=True, text=True, env=env,
    )
    return done.stdout.strip()


def commit(repo: Path, message: str, date: str | None = None) -> str:
    git(repo, "commit", "-q", "--allow-empty", "--no-gpg-sign", "-m", message, date=date)
    return git(repo, "rev-parse", "HEAD")


def hook_env(repo: Path, state: Path) -> dict[str, str]:
    return {**os.environ, "DOTFILES_CHANGE_LOG_REPO": str(repo), "DOTFILES_CHANGE_LOG_STATE": str(state)}


def fire(repo: Path, state: Path, mode: str, payload: dict | None = None) -> str:
    done = subprocess.run(
        [sys.executable, str(HOOK), mode],
        input=json.dumps(payload or {}),
        capture_output=True, text=True, encoding="utf-8", check=True,
        env=hook_env(repo, state),
    )
    if not done.stdout.strip():
        return ""
    return json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"]


def post(repo: Path, state: Path, command: str, tool: str = "Bash") -> str:
    return fire(repo, state, "post-commit", {"tool_name": tool, "tool_input": {"command": command}})


def mark(repo: Path, state: Path, rev: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), "mark", rev],
        capture_output=True, text=True, env=hook_env(repo, state),
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "dotfiles"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    commit(path, "init", date=OLD_DATE)
    return path


@pytest.fixture
def state(tmp_path: Path) -> Path:
    return tmp_path / "state" / "log.json"


def test_post_commit_prompts_once_for_a_new_commit(repo: Path, state: Path) -> None:
    sha = commit(repo, "feat: x")
    out = post(repo, state, 'git commit -F msg.md')
    assert sha in out and STEP_MARK in out and f"mark {sha}" in out, out
    assert post(repo, state, 'git commit -F msg.md') == ""


def test_post_commit_spots_git_dash_c_and_powershell(repo: Path, state: Path) -> None:
    sha = commit(repo, "feat: x")
    assert sha in post(repo, state, f'git -C "{repo}" commit -m x', tool="PowerShell")


def test_post_commit_ignores_other_commands(repo: Path, state: Path) -> None:
    commit(repo, "feat: x")
    assert post(repo, state, "git status") == ""
    assert post(repo, state, "git commit-tree HEAD^{tree}") == ""


def test_failed_commit_leaves_no_fresh_tip(repo: Path, state: Path) -> None:
    assert post(repo, state, "git commit -m nothing-staged") == ""


def test_post_commit_sees_a_worktree_branch(repo: Path, state: Path, tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "feat/x", date=OLD_DATE)
    sha = commit(wt, "feat: in worktree")
    out = post(repo, state, "cd wt && git commit -m x")
    assert sha in out and "feat/x" in out, out


def test_session_start_first_run_records_baseline_silently(repo: Path, state: Path) -> None:
    commit(repo, "feat: before the hook", date="2021-01-01T00:00:00")
    assert fire(repo, state, "session-start") == ""
    assert fire(repo, state, "session-start") == ""


def test_session_start_counts_commits_after_the_baseline(repo: Path, state: Path) -> None:
    fire(repo, state, "session-start")
    commit(repo, "feat: a", date="2030-01-01T00:00:00")
    commit(repo, "feat: b", date="2030-01-02T00:00:00")
    out = fire(repo, state, "session-start")
    assert out.startswith("2 ") and RECONCILE_MARK in out, out


def test_rebased_copy_counts_once(repo: Path, state: Path) -> None:
    fire(repo, state, "session-start")
    git(repo, "checkout", "-q", "-b", "feat/y")
    commit(repo, "feat: y", date="2030-01-01T00:00:00")
    git(repo, "checkout", "-q", "main")
    git(repo, "cherry-pick", "--no-gpg-sign", "--allow-empty", "feat/y", date="2031-01-01T00:00:00")
    out = fire(repo, state, "session-start")
    assert out.startswith("1 "), out


def test_mark_moves_the_baseline(repo: Path, state: Path) -> None:
    fire(repo, state, "session-start")
    commit(repo, "feat: a", date="2030-01-01T00:00:00")
    sha = commit(repo, "feat: b", date="2030-01-02T00:00:00")
    assert mark(repo, state, sha).returncode == 0
    assert fire(repo, state, "session-start") == ""


def test_mark_rejects_an_unknown_commit(repo: Path, state: Path) -> None:
    done = mark(repo, state, "0" * 40)
    assert done.returncode == 1 and "unknown commit" in done.stderr
