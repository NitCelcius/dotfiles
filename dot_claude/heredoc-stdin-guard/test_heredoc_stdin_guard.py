"""Drive heredoc_stdin_guard.py with hook payloads.

Run: uv run --with pytest pytest dot_claude/heredoc-stdin-guard

Covers: `deny` for a heredoc fed to python / uv run python / python3, with or
without the `-` argument, after `cd ... &&`, or with a redirection before the `<<`;
silence for a heredoc fed to node, one that writes a file (`cat > f`, `cat >> f`), `git commit -F`,
ordinary commands, `<<` inside a quoted string, a here-string, and malformed input.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent / "heredoc_stdin_guard.py"

DENIED = [
    "uv run python - <<'EOF'\nprint(1)\nEOF",
    "uv run python -I - <<'PY'\nprint(1)\nPY",
    "uv run python - <<'X'\nX",
    "python3 - <<EOF\nprint(1)\nEOF",
    "python - <<'EOF'\nprint(1)\nEOF",
    "python <<'EOF'\nprint(1)\nEOF",
    "cd /d/source/dotfiles && uv run python - <<'EOF'\nprint(1)\nEOF",
    "python - 2>/dev/null <<'EOF'\nprint(1)\nEOF",
    "uv run python - <<-'EOF'\n\tprint(1)\n\tEOF",
]

ALLOWED = [
    "node - <<'EOF'\nconsole.log(1)\nEOF",
    "cat > a.py <<'EOF'\nx\nEOF",
    "cat >> a.py <<'EOF'\nx\nEOF",
    "cat > python.txt <<'EOF'\nx\nEOF",
    "git commit -F .git/msg.md",
    "git status",
    "uv run python script.py",
    'echo "python - <<EOF"',
    "python - <<< 'print(1)'",
]


def fire(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, check=True)


def fire_command(command: str, tool: str = "Bash") -> str:
    return fire(json.dumps({"tool_name": tool, "tool_input": {"command": command}})).stdout.strip()


@pytest.mark.parametrize("command", DENIED)
def test_denies_heredoc_into_interpreter(command: str) -> None:
    out = json.loads(fire_command(command))["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert out["permissionDecision"] == "deny"
    assert "Write tool" in out["permissionDecisionReason"]


@pytest.mark.parametrize("command", ALLOWED)
def test_allows_other_commands(command: str) -> None:
    assert fire_command(command) == ""


@pytest.mark.parametrize("stdin", ["", "not json", "{}", '{"tool_input": {"command": 5}}'])
def test_silent_on_malformed_input(stdin: str) -> None:
    assert fire(stdin).stdout.strip() == ""
