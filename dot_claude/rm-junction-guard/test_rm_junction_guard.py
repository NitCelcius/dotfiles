"""Drive rm_junction_guard.py with hook payloads against real junctions in tmp_path.

Run: uv run --with pytest pytest dot_claude/rm-junction-guard

Covers: `ask` for each delete form that reaches through a junction (trailing separator,
glob or subpath under the link, cmd `del /s`, an enumerator piped into a delete, a
quoted multi-statement script); silence for deleting a link by name, a folder holding a
link, non-delete commands and malformed input. Also runs the real delete tools once to
confirm that deleting a junction by name keeps its target, which the silence relies on.
Windows only (junctions via mklink /J).
"""

from __future__ import annotations

import json
import os
import shutil
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


def run_raw(stdin: str) -> str:
    done = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def fire(command: str, cwd: Path, tool: str = "Bash") -> str:
    payload = {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd)}
    return run_raw(json.dumps(payload))


def decision(out: str) -> dict:
    return json.loads(out)["hookSpecificOutput"]


@pytest.fixture
def work(tmp_path: Path) -> Path:
    """work/real holds files; work/link and work/holder/inner are junctions to it."""
    real = tmp_path / "real"
    (real / "sub").mkdir(parents=True)
    (real / "keep.txt").write_text("x", encoding="utf-8")
    (real / "sub" / "deep.txt").write_text("x", encoding="utf-8")
    make_junction(tmp_path / "link", real)
    (tmp_path / "holder").mkdir()
    make_junction(tmp_path / "holder" / "inner", real)
    (tmp_path / "plain").mkdir()
    return tmp_path


@pytest.mark.parametrize(
    ("command", "tool"),
    [
        ("rm -rf link/", "Bash"),
        ("rm -rf link/*", "Bash"),
        ("rm -rf link/sub", "Bash"),
        ("rm -rf holder/inner/*", "Bash"),
        ("rm -rf plain && rm -rf link/", "Bash"),
        ("find link -type f | xargs rm -f", "Bash"),
        ("cmd /c del /s /q link", "Bash"),
        ('cmd /c "erase /q link"', "Bash"),
        ("Remove-Item link\\* -Recurse -Force", "PowerShell"),
        ("Get-ChildItem link -Recurse -File | Remove-Item -Force", "PowerShell"),
        ("gci link | ForEach-Object { Remove-Item $_ -Recurse }", "PowerShell"),
        ('powershell -c "Remove-Item plain; Remove-Item link\\*"', "Bash"),
    ],
)
def test_delete_through_junction_asks(work: Path, command: str, tool: str) -> None:
    out = decision(fire(command, work, tool))
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "ask"
    assert "junction" in out["permissionDecisionReason"]
    assert str(work / "real") in out["permissionDecisionReason"]


@pytest.mark.parametrize(
    ("command", "tool"),
    [
        ("rm -rf link", "Bash"),
        ("rm -rf holder", "Bash"),
        ("rm -rf plain/", "Bash"),
        ("rmdir link", "Bash"),
        ("cmd /c rd /s /q link", "Bash"),
        ("Remove-Item -Recurse -Force link", "PowerShell"),
        ("Get-Item link | Remove-Item -Recurse -Force", "PowerShell"),
        ("git rm -r link/", "Bash"),
        ("grep -r rd link/", "Bash"),
        ("echo del link/", "Bash"),
        ("ls link/", "Bash"),
        ("rm -rf does-not-exist/ $UNSET_VAR/x", "Bash"),
    ],
)
def test_delete_not_through_junction_is_silent(work: Path, command: str, tool: str) -> None:
    assert fire(command, work, tool) == ""


@pytest.mark.parametrize("stdin", ["", "not json", "[]", '{"tool_input": {}}', '{"tool_input": {"command": 3}}'])
def test_malformed_stdin_is_silent(stdin: str) -> None:
    assert run_raw(stdin) == ""


def _tool(name: str, *argv: str) -> list[str] | None:
    path = shutil.which(name)
    return [path, *argv] if path else None


# The hook stays silent on deleting a link by name because these tools remove only the
# link. Recheck that here so a tool that starts following junctions fails loudly.
DELETE_BY_NAME = {
    "rm -rf": lambda: _tool("rm", "-rf", "link"),
    "pwsh Remove-Item -Recurse": lambda: _tool("pwsh", "-NoProfile", "-NonInteractive", "-Command", "Remove-Item -Recurse -Force link"),
    "powershell Remove-Item -Recurse": lambda: _tool("powershell", "-NoProfile", "-NonInteractive", "-Command", "Remove-Item -Recurse -Force link"),
    "cmd rd /s /q": lambda: ["cmd", "/c", "rd /s /q link"],
}


@pytest.mark.parametrize("name", list(DELETE_BY_NAME))
def test_deleting_junction_by_name_keeps_target(work: Path, name: str) -> None:
    argv = DELETE_BY_NAME[name]()
    if argv is None:
        pytest.skip(f"{name.split()[0]} not on PATH")
    subprocess.run(argv, cwd=work, check=True, capture_output=True)
    assert not os.path.lexists(work / "link")
    assert (work / "real" / "keep.txt").exists()
    assert (work / "real" / "sub" / "deep.txt").exists()
