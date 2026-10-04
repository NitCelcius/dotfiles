"""Exercise the wrapper and documented hook adapter against real hyperfine.

Run: uv run --with pytest pytest dot_claude/skills/benchmarking
Requires hyperfine on PATH; CI installs it before the repository test suite.
"""

from __future__ import annotations

import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest

BENCH = Path(__file__).with_name("bench.py")
SKILL = BENCH.parent.parent / "SKILL.md"
pytestmark = pytest.mark.skipif(shutil.which("hyperfine") is None, reason="hyperfine is required")


def command(*args: str | Path) -> str:
    return shlex.join([Path(sys.executable).as_posix(), *(str(a).replace("\\", "/") for a in args)])


def script(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def bench(out: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BENCH), "--out", str(out), "--cwd", str(cwd or out.parent),
         "--", "--shell=none", "--runs", "2", *args],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )


def test_replays_input_for_both_cases_and_warmups(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture space"
    fixture.mkdir()
    payload = b'{"command":"example","cwd":"fixture"}\n'
    (fixture / "payload.json").write_bytes(payload)
    target = script(fixture / "hook.py", """import sys
from pathlib import Path
payload = sys.stdin.buffer.read()
assert payload == Path('payload.json').read_bytes(), repr(payload)
with Path('seen.txt').open('a') as f:
    f.write(sys.argv[1] + '\\n')
sys.stderr.buffer.write(b'warning: \\xff\\n')
""")
    out = tmp_path / "result"
    done = bench(out, "--warmup", "1", "--input", "payload.json", "--command-name", "before",
                 command(target, "A"), "--command-name", "after", command(target, "B"), cwd=fixture)
    assert done.returncode == 0, done.stderr
    seen = (fixture / "seen.txt").read_text().splitlines()
    assert seen.count("A") == seen.count("B") == 3
    results = json.loads((out / "results.json").read_text())["results"]
    assert [r["command"] for r in results] == ["before", "after"]
    assert all(len(r["times"]) == 2 and r["exit_codes"] == [0, 0] for r in results)
    manifest = json.loads((out / "run.json").read_text())
    assert Path(manifest["cwd"]) == fixture.resolve()
    assert manifest["exit_code"] == 0 and manifest["hyperfine_version"].startswith("hyperfine ")
    assert "before" in (out / "summary.md").read_text()


def test_prepare_failure_prevents_timed_work(tmp_path: Path) -> None:
    prepare = script(tmp_path / "prepare.py", "raise SystemExit(17)\n")
    target = script(tmp_path / "target.py", "from pathlib import Path\nPath('ran').touch()\n")
    out = tmp_path / "result"
    done = bench(out, "--prepare", command(prepare), command(target))
    assert done.returncode != 0
    assert not (tmp_path / "ran").exists()
    assert json.loads((out / "run.json").read_text())["exit_code"] != 0
    assert b"preparation command" in (out / "stderr.log").read_bytes()


@pytest.mark.parametrize("actual_exit", [0, 2, 3])
def test_documented_adapter_requires_exact_exit(tmp_path: Path, actual_exit: int) -> None:
    adapter = script(tmp_path / "check_block.py", SKILL.read_text(encoding="utf-8").split("```python\n", 1)[1].split("```", 1)[0])
    target = script(tmp_path / "hook.py", f"import sys\nassert sys.stdin.read() == '{{}}'\nsys.exit({actual_exit})\n")
    (tmp_path / "payload.json").write_text("{}")
    out = tmp_path / "result"
    done = bench(out, "--input", "payload.json", command(adapter, Path(sys.executable).as_posix(), target))
    assert (done.returncode == 0) == (actual_exit == 2), done.stdout + done.stderr


def test_refuses_to_overwrite_results(tmp_path: Path) -> None:
    out = tmp_path / "result"
    out.mkdir()
    previous = out / "summary.md"
    previous.write_text("keep me")
    target = script(tmp_path / "target.py", "from pathlib import Path\nPath('ran').touch()\n")
    done = bench(out, command(target))
    assert done.returncode != 0 and previous.read_text() == "keep me"
    assert not (tmp_path / "ran").exists()


def test_zero_exit_without_measurements_is_not_success(tmp_path: Path) -> None:
    out = tmp_path / "result"
    done = bench(out, "--help")
    assert done.returncode != 0
    assert json.loads((out / "run.json").read_text())["exit_code"] != 0


def test_rejects_export_override(tmp_path: Path) -> None:
    out = tmp_path / "result"
    done = bench(out, "--export-json=elsewhere.json", "ignored")
    assert done.returncode != 0 and not out.exists()
