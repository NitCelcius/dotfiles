"""Drive rm_junction_guard.py with hook payloads against real junctions in tmp_path.

Run: uv run --with pytest pytest dot_claude/rm-junction-guard

Covers: silent on non-delete commands, `git rm`, plain directories and malformed
input; `ask` when the target is a junction, holds a junction, is pointed at by a
junction, or is mentioned by a shim script. Windows only (junctions via mklink /J).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent / "rm_junction_guard.py"

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="junctions are Windows-only")


def make_junction(link: Path, target: Path) -> None:
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=True,
        capture_output=True,
    )


def run_raw(stdin: str, home: Path) -> str:
    # Point every search root the hook reads at an empty home so the run is hermetic.
    env = {k: v for k, v in os.environ.items() if k != "PNPM_HOME"}
    env.update(HOME=str(home), USERPROFILE=str(home), LOCALAPPDATA=str(home))
    done = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return done.stdout.strip()


def fire(command: str, cwd: Path, home: Path, tool: str = "Bash") -> str:
    payload = {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd)}
    return run_raw(json.dumps(payload), home)


def decision(out: str) -> dict:
    return json.loads(out)["hookSpecificOutput"]


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "home"
    path.mkdir()
    return path


@pytest.fixture
def work(tmp_path: Path) -> Path:
    path = tmp_path / "work"
    path.mkdir()
    return path


def test_non_delete_command_is_silent(work: Path, home: Path) -> None:
    (work / "d").mkdir()
    assert fire("ls d", work, home) == ""


def test_git_rm_is_silent(work: Path, home: Path) -> None:
    target = work / "d"
    target.mkdir()
    make_junction(work / "link", target)
    assert fire("git rm -r d", work, home) == ""


def test_plain_directory_is_silent(work: Path, home: Path) -> None:
    (work / "plain").mkdir()
    (work / "plain" / "f.txt").write_text("x", encoding="utf-8")
    assert fire("rm -rf plain", work, home) == ""


def test_junction_target_asks(work: Path, home: Path) -> None:
    real = work / "real"
    real.mkdir()
    make_junction(work / "link", real)
    out = decision(fire("rm -rf link", work, home))
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "ask"
    assert "itself a junction" in out["permissionDecisionReason"]


def test_powershell_remove_item_on_junction_asks(work: Path, home: Path) -> None:
    real = work / "real"
    real.mkdir()
    make_junction(work / "link", real)
    out = decision(fire("Remove-Item -Recurse -Force link", work, home, tool="PowerShell"))
    assert out["permissionDecision"] == "ask"


def test_directory_containing_junction_asks(work: Path, home: Path) -> None:
    outside = work / "outside"
    outside.mkdir()
    holder = work / "holder"
    holder.mkdir()
    make_junction(holder / "inner", outside)
    out = decision(fire("rm -rf holder", work, home))
    assert out["permissionDecision"] == "ask"
    assert "contains a junction" in out["permissionDecisionReason"]


def test_directory_pointed_at_by_junction_asks(work: Path, home: Path) -> None:
    target = work / "store"
    target.mkdir()
    (work / "elsewhere").mkdir()
    make_junction(work / "elsewhere" / "link", target)
    out = decision(fire("rm -rf store", work, home))
    assert out["permissionDecision"] == "ask"
    assert "points into" in out["permissionDecisionReason"]


def test_directory_referenced_by_shim_asks(work: Path, home: Path) -> None:
    target = work / "pkg"
    target.mkdir()
    (work / "tool.cmd").write_text(f'@"{target}\\bin\\tool.js" %*\n', encoding="utf-8")
    out = decision(fire("rm -rf pkg", work, home))
    assert out["permissionDecision"] == "ask"
    assert "tool.cmd" in out["permissionDecisionReason"]


def test_shim_with_relative_reference_asks(work: Path, home: Path) -> None:
    target = work / "pkg"
    target.mkdir()
    (work / "tool").write_text('exec node "$basedir/pkg/bin/tool.js" "$@"\n', encoding="utf-8")
    out = decision(fire("rm -rf pkg", work, home))
    assert out["permissionDecision"] == "ask"


@pytest.mark.parametrize("stdin", ["", "not json", "[]", '{"tool_input": {}}', '{"tool_input": {"command": 3}}'])
def test_malformed_stdin_is_silent(stdin: str, home: Path) -> None:
    assert run_raw(stdin, home) == ""


def test_unresolvable_target_is_silent(work: Path, home: Path) -> None:
    assert fire("rm -rf does-not-exist $UNSET_VAR/x", work, home) == ""
