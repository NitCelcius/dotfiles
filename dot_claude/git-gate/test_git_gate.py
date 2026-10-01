"""Drive git_gate.py with hook payloads against real repos with a bare remote in tmp_path.

Run: uv run --with pytest pytest dot_claude/git-gate

Covers: silence for a forced delete of a local-only branch and of a fully pushed one,
`ask` for a remote-backed branch with unpushed commits (found through `cd`, `git -C`,
the PowerShell tool and a multi-branch delete), `ask` for a branch outside any repo;
`deny` for a `+refspec` push, `ask` for a `:refspec` or `--delete` push; and under
`--unattended`, `deny` for each of those and for anything a live `permissions.ask`
rule matches, with silence for what the gate clears.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent / "git_gate.py"


@pytest.fixture(scope="module")
def env(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Hermetic git and HOME: no user config, no signing, a settings.json with two ask rules."""
    tmp_path = tmp_path_factory.mktemp("env")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"ask": ["Bash(gh pr create*)", "Bash(git reset --hard*)"]}}),
        encoding="utf-8",
    )
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = t\n\temail = t@example.com\n[commit]\n\tgpgsign = false\n", encoding="utf-8")
    result = dict(os.environ)
    result.update(
        HOME=str(home),
        USERPROFILE=str(home),
        GIT_CONFIG_GLOBAL=str(gitconfig),
        GIT_CONFIG_NOSYSTEM="1",
    )
    return result


def git(cwd: Path, env: dict[str, str], *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory, env: dict[str, str]) -> Path:
    """A clone with `pushed` (fully pushed), `ahead` (pushed, plus one local commit) and `local` (never pushed).

    Shared by the module: the hook only reads the repo, and no test runs the commands it judges.
    """
    tmp_path = tmp_path_factory.mktemp("repo")
    remote = tmp_path / "remote.git"
    work = tmp_path / "work tree"
    git(tmp_path, env, "init", "-q", "--bare", "-b", "main", str(remote))
    git(tmp_path, env, "clone", "-q", str(remote), str(work))
    git(work, env, "commit", "-q", "--allow-empty", "-m", "base")
    git(work, env, "push", "-q", "origin", "HEAD:main")
    for name in ("pushed", "ahead"):
        git(work, env, "switch", "-q", "-c", name, "main")
        git(work, env, "commit", "-q", "--allow-empty", "-m", name)
        git(work, env, "push", "-q", "-u", "origin", name)
    git(work, env, "switch", "-q", "ahead")
    git(work, env, "commit", "-q", "--allow-empty", "-m", "unpushed")
    git(work, env, "switch", "-q", "-c", "local", "main")
    git(work, env, "commit", "-q", "--allow-empty", "-m", "local only")
    git(work, env, "switch", "-q", "main")
    return work


def fire(command: str, cwd: Path, env: dict[str, str], tool: str = "Bash", unattended: bool = False) -> dict | None:
    payload = {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd)}
    args = [sys.executable, str(HOOK), *(["--unattended"] if unattended else [])]
    done = subprocess.run(args, input=json.dumps(payload), capture_output=True, text=True, check=True, env=env)
    out = done.stdout.strip()
    return json.loads(out)["hookSpecificOutput"] if out else None


def decision(output: dict | None) -> str | None:
    return output["permissionDecision"] if output else None


@pytest.mark.parametrize("command", ["git branch -D local", "git branch -D pushed", "git branch -d -f local"])
def test_forced_delete_without_unpushed_remote_work_is_silent(repo: Path, env: dict[str, str], command: str) -> None:
    assert fire(command, repo, env) is None


def test_remote_backed_branch_with_unpushed_commits_asks(repo: Path, env: dict[str, str]) -> None:
    output = fire("git branch -D ahead", repo, env)
    assert decision(output) == "ask"
    assert "`ahead`" in output["permissionDecisionReason"]
    assert "1 commit" in output["permissionDecisionReason"]


@pytest.mark.parametrize(
    "template",
    [
        'cd "{repo}" && git branch -D ahead',
        'git -C "{repo}" branch -D ahead',
        'cd "{repo}"\ngit branch -D local ahead',
        'bash -c \'cd "{repo}" && git branch --delete --force ahead\'',
    ],
)
def test_repo_is_found_through_cd_and_dash_c(repo: Path, env: dict[str, str], tmp_path: Path, template: str) -> None:
    command = template.format(repo=repo.as_posix())
    assert decision(fire(command, tmp_path, env)) == "ask"


def test_powershell_tool_is_gated_too(repo: Path, env: dict[str, str], tmp_path: Path) -> None:
    command = f'Set-Location "{repo}"; git branch -D ahead'
    assert decision(fire(command, tmp_path, env, tool="PowerShell")) == "ask"


def test_plain_delete_and_remote_tracking_delete_are_silent(repo: Path, env: dict[str, str]) -> None:
    assert fire("git branch -d ahead", repo, env) is None
    assert fire("git branch -D -r origin/ahead", repo, env) is None


def test_branch_outside_a_repo_asks(env: dict[str, str], tmp_path: Path) -> None:
    assert decision(fire("git branch -D ahead", tmp_path, env)) == "ask"


def test_missing_branch_is_left_to_git(repo: Path, env: dict[str, str]) -> None:
    assert fire("git branch -D no-such-branch", repo, env) is None


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("git push origin +main", "deny"),
        ("git push origin feat +main:main", "deny"),
        ("git push origin :feat", "ask"),
        ("git push --delete origin feat", "ask"),
        ("git push -d origin feat", "ask"),
        ("git push -u origin feat", None),
        ("git push", None),
    ],
)
def test_push_refspecs(repo: Path, env: dict[str, str], command: str, expected: str | None) -> None:
    assert decision(fire(command, repo, env)) == expected


def test_non_git_command_is_silent(repo: Path, env: dict[str, str]) -> None:
    assert fire("gh pr create --draft", repo, env) is None


@pytest.mark.parametrize(
    "command",
    [
        "git branch -D ahead",
        "git push origin +main",
        "git push origin :feat",
        "gh pr create --draft --title x",
        "git -C . reset --hard HEAD~1",
        "git status && gh pr create",
    ],
)
def test_unattended_denies_what_would_prompt(repo: Path, env: dict[str, str], command: str) -> None:
    output = fire(command, repo, env, unattended=True)
    assert decision(output) == "deny"
    assert "Unattended run" in output["permissionDecisionReason"]


@pytest.mark.parametrize("command", ["git branch -D local", "git push -u origin feat", "git rebase origin/main", "ls"])
def test_unattended_is_silent_on_what_the_gate_clears(repo: Path, env: dict[str, str], command: str) -> None:
    assert fire(command, repo, env, unattended=True) is None


@pytest.mark.parametrize("stdin", ["", "not json", "{}", '{"tool_input": {"command": 5}}'])
def test_malformed_input_is_silent(env: dict[str, str], stdin: str) -> None:
    done = subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, check=True, env=env)
    assert done.stdout == ""
