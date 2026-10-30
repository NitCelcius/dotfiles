"""Tests for verify_on_stop.py: the parsers as unit tests, the hook end to end.

Run: uv run --with pytest pytest dot_claude/verify-on-stop

The parser cases live in the hook itself (`--selftest` runs the same tables). The
end-to-end tests drive the hook against a throwaway git repo and cover what the
tables cannot: that the guard really skips an unchanged tree, notices an edit to an
untracked file, blocks once on a failure, and never blocks twice in a row. The
first two were real bugs caught here before the hook was wired into settings.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import verify_on_stop

HOOK = Path(__file__).resolve().parent / "verify_on_stop.py"
PYTHON = f'"{sys.executable}"'

BLOCK = """# CLAUDE.md

## Verification

- **quick** (task close-out, aim for under 30s): `{cmd}`
- **full** (before a commit or PR): `{cmd}`
- **Out of scope**: nothing
"""

FAILING_COMMAND = f"{PYTHON} -c \"import sys; print('boom detail'); sys.exit(3)\""


def parse_cases(cases: list[tuple]) -> list:
    return [pytest.param(*case[1:], id=case[0]) for case in cases]


@pytest.mark.parametrize("text, expected", parse_cases(verify_on_stop.SELFTEST_CASES))
def test_parse_quick_command(text: str, expected: str | None) -> None:
    assert verify_on_stop.parse_quick_command(text) == expected


@pytest.mark.parametrize("status_z, expected", parse_cases(verify_on_stop.UNTRACKED_CASES))
def test_untracked_paths(status_z: str, expected: list[str]) -> None:
    assert verify_on_stop.untracked_paths(status_z) == sorted(expected)


@pytest.mark.parametrize("status_z, expected", parse_cases(verify_on_stop.CHANGED_CASES))
def test_changed_paths(status_z: str, expected: list[str]) -> None:
    assert verify_on_stop.changed_paths(status_z) == sorted(expected)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


def fire(repo: Path, data_root: Path, stop_hook_active: bool = False) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_VERIFY_DATA_ROOT": str(data_root), "PYTHONIOENCODING": "utf-8"}
    payload = {"cwd": str(repo), "hook_event_name": "Stop"}
    if stop_hook_active:
        payload["stop_hook_active"] = True
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=120,
    )


def write_block(repo: Path, command: str) -> None:
    (repo / "CLAUDE.md").write_text(BLOCK.format(cmd=command), encoding="utf-8")


def counting_command(marker: Path) -> str:
    return f"{PYTHON} -c \"open(r'{marker}','a').write('x')\""


def recording_command(args_log: Path) -> str:
    return (
        f'{PYTHON} -c "import sys,io;'
        f"io.open(r'{args_log}','a',encoding='utf-8')"
        '.write(\' \'.join(sys.argv[1:])+chr(10))" {changed:*.py}'
    )


def run_count(marker: Path) -> int:
    return marker.read_text().count("x") if marker.exists() else 0


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "user.name", "t")
    git(path, "config", "commit.gpgsign", "false")
    (path / "seed.txt").write_text("seed\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "seed")
    return path


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    return tmp_path / "state"


def test_no_claude_md_allows_stop(repo: Path, data_root: Path) -> None:
    r = fire(repo, data_root)
    assert r.returncode == verify_on_stop.EXIT_ALLOW_STOP, r.stderr


def test_no_verification_block_allows_stop(repo: Path, data_root: Path) -> None:
    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n## Commands\n\n- `npm test`\n", encoding="utf-8")
    r = fire(repo, data_root)
    assert r.returncode == verify_on_stop.EXIT_ALLOW_STOP, r.stderr


def test_passing_quick_allows_stop_and_runs_the_command(repo: Path, data_root: Path) -> None:
    marker = repo / "ran.log"
    write_block(repo, counting_command(marker))
    r = fire(repo, data_root)
    assert r.returncode == verify_on_stop.EXIT_ALLOW_STOP, r.stderr
    assert run_count(marker) == 1


def test_unchanged_tree_skips_rerun(repo: Path, data_root: Path) -> None:
    marker = repo / "ran.log"
    write_block(repo, counting_command(marker))
    fire(repo, data_root)
    r = fire(repo, data_root)
    assert r.returncode == verify_on_stop.EXIT_ALLOW_STOP, r.stderr
    assert run_count(marker) == 1


def test_tracked_edit_reruns(repo: Path, data_root: Path) -> None:
    marker = repo / "ran.log"
    write_block(repo, counting_command(marker))
    fire(repo, data_root)
    (repo / "seed.txt").write_text("seed changed\n", encoding="utf-8")
    fire(repo, data_root)
    assert run_count(marker) == 2


def test_committing_a_passed_tree_keeps_the_cached_pass(repo: Path, data_root: Path) -> None:
    marker = repo / "ran.log"
    write_block(repo, counting_command(marker))
    fire(repo, data_root)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "checkpoint")
    r = fire(repo, data_root)
    assert r.returncode == verify_on_stop.EXIT_ALLOW_STOP, r.stderr
    assert run_count(marker) == 1


def test_untracked_edit_invalidates_cached_pass_and_blocks(repo: Path, data_root: Path) -> None:
    # CLAUDE.md is untracked here on purpose: editing an untracked file must
    # still invalidate the cached pass, or a new module never gets verified.
    write_block(repo, counting_command(repo / "ran.log"))
    fire(repo, data_root)
    write_block(repo, FAILING_COMMAND)
    r = fire(repo, data_root)
    assert r.returncode == verify_on_stop.EXIT_BLOCK_STOP, r.stderr
    assert "boom detail" in r.stderr


def test_same_failing_state_twice_allows_the_second_stop(repo: Path, data_root: Path) -> None:
    write_block(repo, FAILING_COMMAND)
    first = fire(repo, data_root)
    second = fire(repo, data_root)
    assert first.returncode == verify_on_stop.EXIT_BLOCK_STOP, first.stderr
    assert second.returncode == verify_on_stop.EXIT_ALLOW_STOP, second.stderr


def test_stop_hook_active_allows_stop(repo: Path, data_root: Path) -> None:
    write_block(repo, FAILING_COMMAND)
    r = fire(repo, data_root, stop_hook_active=True)
    assert r.returncode == verify_on_stop.EXIT_ALLOW_STOP, r.stderr


def test_changed_placeholder_passes_only_matching_files(repo: Path, data_root: Path) -> None:
    args_log = repo / "args.log"
    write_block(repo, recording_command(args_log))
    (repo / "alpha.py").write_text("a = 1\n", encoding="utf-8")
    (repo / "notes.md").write_text("# notes\n", encoding="utf-8")
    r = fire(repo, data_root)
    recorded = args_log.read_text(encoding="utf-8") if args_log.exists() else ""
    assert r.returncode == verify_on_stop.EXIT_ALLOW_STOP, r.stderr
    assert "alpha.py" in recorded
    assert "notes.md" not in recorded


def test_changed_placeholder_skips_the_command_when_only_a_nonmatching_file_is_dirty(
    repo: Path, data_root: Path
) -> None:
    # Committing first is the point: {changed} means "differs from HEAD", not
    # "edited since the last run", so an uncommitted alpha.py would still match.
    args_log = repo / "args.log"
    write_block(repo, recording_command(args_log))
    (repo / "alpha.py").write_text("a = 1\n", encoding="utf-8")
    (repo / "notes.md").write_text("# notes\n", encoding="utf-8")
    fire(repo, data_root)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "checkpoint")
    before = args_log.read_text(encoding="utf-8")
    (repo / "notes.md").write_text("# notes, revised\n", encoding="utf-8")
    r = fire(repo, data_root)
    assert r.returncode == verify_on_stop.EXIT_ALLOW_STOP, r.stderr
    assert args_log.read_text(encoding="utf-8") == before


def test_root_and_nested_checks_are_cached_separately(repo: Path, data_root: Path, tmp_path: Path) -> None:
    # Markers live outside the checkout so running a check does not change the tree.
    sub = repo / "sub"
    sub.mkdir()
    root_marker, sub_marker = tmp_path / "root.log", tmp_path / "sub.log"
    write_block(repo, counting_command(root_marker))
    write_block(sub, counting_command(sub_marker))
    for _ in range(2):
        assert fire(repo, data_root).returncode == verify_on_stop.EXIT_ALLOW_STOP
        assert fire(sub, data_root).returncode == verify_on_stop.EXIT_ALLOW_STOP
    assert run_count(root_marker) == 1
    assert run_count(sub_marker) == 1


def test_failure_in_one_scope_does_not_suppress_another(repo: Path, data_root: Path, tmp_path: Path) -> None:
    sub = repo / "sub"
    sub.mkdir()
    root_marker = tmp_path / "root.log"
    write_block(repo, counting_command(root_marker))
    write_block(sub, FAILING_COMMAND)
    assert fire(sub, data_root).returncode == verify_on_stop.EXIT_BLOCK_STOP
    assert fire(repo, data_root).returncode == verify_on_stop.EXIT_ALLOW_STOP
    assert run_count(root_marker) == 1


def test_not_a_git_repo_allows_stop(tmp_path: Path, data_root: Path) -> None:
    bare = tmp_path / "notrepo"
    bare.mkdir()
    write_block(bare, "exit 1")
    r = fire(bare, data_root)
    assert r.returncode == verify_on_stop.EXIT_ALLOW_STOP, r.stderr


PYPROJECT_WITH_PATH_SOURCE = """[project]
name = "demo"
version = "0.1.0"
dependencies = ["lib"]

[tool.uv.sources]
lib = { path = "../lib" }
"""


@pytest.fixture
def uv_repo(repo: Path, tmp_path: Path) -> Path:
    """A uv project whose `../lib` source resolves from the main checkout only."""
    (tmp_path / "lib").mkdir()
    (repo / "pyproject.toml").write_text(PYPROJECT_WITH_PATH_SOURCE, encoding="utf-8")
    (repo / "uv.lock").write_text("lock\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "uv project")
    return repo


def add_worktree(repo: Path, path: Path) -> Path:
    git(repo, "worktree", "add", "-q", str(path), "-b", path.name)
    return path


def test_nested_worktree_uses_the_main_checkout(uv_repo: Path) -> None:
    wt = add_worktree(uv_repo, uv_repo / ".worktree" / "wt")
    assert verify_on_stop.main_checkout_uv_project(wt) == uv_repo.resolve()


def test_main_checkout_itself_is_left_alone(uv_repo: Path) -> None:
    assert verify_on_stop.main_checkout_uv_project(uv_repo) is None


def test_sibling_worktree_that_resolves_the_source_is_left_alone(uv_repo: Path, tmp_path: Path) -> None:
    wt = add_worktree(uv_repo, tmp_path / "repo-wt")
    assert verify_on_stop.main_checkout_uv_project(wt) is None


def test_worktree_with_a_different_lock_is_left_alone(uv_repo: Path) -> None:
    wt = add_worktree(uv_repo, uv_repo / ".worktree" / "wt")
    (wt / "uv.lock").write_text("other lock\n", encoding="utf-8")
    assert verify_on_stop.main_checkout_uv_project(wt) is None


def test_installed_project_is_left_alone(uv_repo: Path) -> None:
    wt = add_worktree(uv_repo, uv_repo / ".worktree" / "wt")
    packaged = PYPROJECT_WITH_PATH_SOURCE + '\n[build-system]\nrequires = ["hatchling"]\n'
    for checkout in (uv_repo, wt):
        (checkout / "pyproject.toml").write_text(packaged, encoding="utf-8")
    assert verify_on_stop.main_checkout_uv_project(wt) is None


def test_hook_runs_quick_with_uv_project_in_a_nested_worktree(
    uv_repo: Path, data_root: Path, tmp_path: Path
) -> None:
    wt = add_worktree(uv_repo, uv_repo / ".worktree" / "wt")
    seen = tmp_path / "uv_project.txt"
    write_block(wt, f"{PYTHON} -c \"import os; open(r'{seen}','w').write(os.environ.get('UV_PROJECT',''))\"")
    r = fire(wt, data_root)
    assert r.returncode == verify_on_stop.EXIT_ALLOW_STOP, r.stderr
    assert Path(seen.read_text()).resolve() == uv_repo.resolve()
