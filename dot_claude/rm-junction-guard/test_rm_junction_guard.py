"""Drive rm_junction_guard.py with hook payloads against real junctions in tmp_path.

Run: uv run --with pytest pytest dot_claude/rm-junction-guard

Covers: `ask` for each delete form that reaches through a junction (trailing separator,
glob or subpath under the link, cmd `del /s`, an enumerator piped into a delete, a
quoted multi-statement script) and for a guarded name (`node_modules`, `.venv`) whose
contents a global shim runs; silence for deleting a link by name, a folder holding a
link, a project node_modules no shim runs, non-delete commands and malformed input.
Also runs the real delete tools once to
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


def run_raw(stdin: str, home: Path, pnpm_home: Path | None = None) -> str:
    # Point every shim directory the hook reads into `home` so the run is hermetic.
    env = {k: v for k, v in os.environ.items() if k != "PNPM_HOME"}
    env.update(HOME=str(home), USERPROFILE=str(home), LOCALAPPDATA=str(home), APPDATA=str(home))
    if pnpm_home:
        env["PNPM_HOME"] = str(pnpm_home)
    done = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return done.stdout.strip()


def fire(command: str, cwd: Path, tool: str = "Bash", pnpm_home: Path | None = None, home: Path | None = None) -> str:
    payload = {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd)}
    return run_raw(json.dumps(payload), home or cwd / "home", pnpm_home)


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
    (tmp_path / "home").mkdir()
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


@pytest.fixture
def pnpm(tmp_path: Path) -> Path:
    """A global pnpm layout: shims in pnpm/ run packages in pnpm/global/5/node_modules."""
    root = tmp_path / "pnpm"
    (root / "global" / "5" / "node_modules" / "foo" / "bin").mkdir(parents=True)
    (root / "foo.cmd").write_text('@"%~dp0\\global\\5\\node_modules\\foo\\bin\\foo.js" %*\n', encoding="utf-8")
    (root / "foo").write_text('exec node "$basedir/global/5/node_modules/foo/bin/foo.js" "$@"\n', encoding="utf-8")
    (tmp_path / "home").mkdir(exist_ok=True)
    return root


@pytest.mark.parametrize(
    "command",
    ["rm -rf node_modules", "rm -rf node_modules/foo", "Remove-Item -Recurse -Force node_modules"],
)
def test_delete_under_shim_fed_name_with_global_shim_asks(pnpm: Path, command: str) -> None:
    out = decision(fire(command, pnpm / "global" / "5", pnpm_home=pnpm))
    assert out["permissionDecision"] == "ask"
    assert "foo.cmd" in out["permissionDecisionReason"]


def test_venv_referenced_by_local_bin_shim_asks(tmp_path: Path) -> None:
    venv = tmp_path / "proj" / ".venv"
    (venv / "Scripts").mkdir(parents=True)
    bin_dir = tmp_path / "home" / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "tool.cmd").write_text(f'@"{venv}\\Scripts\\python.exe" -m tool %*\n', encoding="utf-8")
    out = decision(fire("rm -rf .venv", tmp_path / "proj", home=tmp_path / "home"))
    assert "tool.cmd" in out["permissionDecisionReason"]


def test_project_node_modules_is_silent(pnpm: Path, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    (project / "node_modules" / "foo").mkdir(parents=True)
    assert fire("rm -rf node_modules", project, pnpm_home=pnpm) == ""


def test_node_modules_deeper_in_shim_path_is_silent(pnpm: Path) -> None:
    # codex-style shim: node_modules appears only under global/5/.pnpm, not beside the shim.
    (pnpm / "foo.cmd").write_text('@"%~dp0\\global\\5\\.pnpm\\foo@1\\node_modules\\foo\\bin\\foo.js" %*\n', encoding="utf-8")
    (pnpm / "foo").unlink()
    (pnpm / "node_modules").mkdir()
    assert fire("rm -rf node_modules", pnpm, pnpm_home=pnpm) == ""


def test_shim_target_without_shim_fed_name_is_silent(pnpm: Path) -> None:
    # The shim runs global/5/..., but "global" is not a guarded name.
    assert fire("rm -rf global", pnpm, pnpm_home=pnpm) == ""


@pytest.mark.parametrize("stdin", ["", "not json", "[]", '{"tool_input": {}}', '{"tool_input": {"command": 3}}'])
def test_malformed_stdin_is_silent(stdin: str, tmp_path: Path) -> None:
    assert run_raw(stdin, tmp_path) == ""


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
