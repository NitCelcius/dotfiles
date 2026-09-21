#!/usr/bin/env python3
"""Regression test for .githooks/pre-commit.

Builds a scratch bare origin and clone, copies the hook in, and runs it with `sh`.
Run: `uv run python .githooks/test_pre_commit.py`. Touches only a temp directory.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK_DIR = Path(__file__).parent
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
}


def git(repo: Path, *args: str) -> None:
    env = {**os.environ, **GIT_ENV}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def commit_file(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", name)


class PreCommitTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        origin, self.repo = root / "origin.git", root / "clone"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
        subprocess.run(["git", "clone", "-q", str(origin), str(self.repo)], check=True, capture_output=True)
        git(self.repo, "checkout", "-q", "-b", "main")
        commit_file(self.repo, "base")
        git(self.repo, "push", "-q", "origin", "main")
        (self.repo / ".githooks").mkdir()
        shutil.copy(HOOK_DIR / "pre-commit", self.repo / ".githooks" / "pre-commit")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def enable_diverged_guard(self) -> None:
        (self.repo / ".githooks" / "guard-diverged").write_text("")

    def diverge(self) -> None:
        git(self.repo, "switch", "-q", "-c", "feat/old")
        commit_file(self.repo, "a")
        git(self.repo, "switch", "-q", "main")
        commit_file(self.repo, "b")
        git(self.repo, "push", "-q", "origin", "main")
        git(self.repo, "switch", "-q", "feat/old")

    def run_hook(self, **env: str) -> int:
        result = subprocess.run(
            ["sh", str(self.repo / ".githooks" / "pre-commit")],
            cwd=self.repo,
            capture_output=True,
            env={**os.environ, **env},
        )
        return result.returncode

    def test_refuses_on_main(self) -> None:
        self.assertEqual(self.run_hook(), 1)

    def test_allow_main_escape_hatch(self) -> None:
        self.assertEqual(self.run_hook(ALLOW_MAIN="1"), 0)

    def test_allows_branch_from_origin_main(self) -> None:
        git(self.repo, "switch", "-q", "-c", "feat/x", "origin/main")
        commit_file(self.repo, "a")
        self.enable_diverged_guard()
        self.assertEqual(self.run_hook(), 0)

    def test_refuses_diverged_when_opted_in(self) -> None:
        self.diverge()
        self.enable_diverged_guard()
        self.assertEqual(self.run_hook(), 1)

    def test_diverged_ignored_without_opt_in(self) -> None:
        self.diverge()
        self.assertEqual(self.run_hook(), 0)

    def test_allow_diverged_escape_hatch(self) -> None:
        self.diverge()
        self.enable_diverged_guard()
        self.assertEqual(self.run_hook(ALLOW_DIVERGED="1"), 0)

    def test_detached_head_ignored(self) -> None:
        self.diverge()
        self.enable_diverged_guard()
        git(self.repo, "checkout", "-q", "--detach")
        self.assertEqual(self.run_hook(), 0)


if __name__ == "__main__":
    unittest.main()
