"""Drive bench.py with tiny Python commands as the cases.

Run: uv run --with pytest pytest dot_claude/skills/benchmarking

Covers interleaving (every round runs every case, order varies), warmup rows kept out
of the summary, a failing case marked invalid, stderr output not breaking a run, the
refusal to reuse an output folder, and the host and path records in env.json.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parent / "bench.py"
PY = Path(sys.executable).as_posix()
OK = f'"{PY}" -c "pass"'
FAIL = f'"{PY}" -c "import sys; sys.exit(3)"'
NOISY_STDERR = f'"{PY}" -c "import sys; sys.stderr.write(\'warn\\n\')"'


def bench(out: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BENCH), "--out", str(out), *args],
        capture_output=True, text=True,
    )


def rows(out: Path) -> list[dict]:
    with (out / "runs.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def out(tmp_path: Path) -> Path:
    return tmp_path / "result"


def test_rounds_interleave_and_shuffle(out: Path) -> None:
    done = bench(out, "--case", f"A={OK}", "--case", f"B={OK}", "--case", f"C={OK}",
                 "--rounds", "8", "--warmup", "0", "--seed", "1")
    assert done.returncode == 0, done.stderr
    runs = rows(out)
    by_round: dict[str, list[str]] = {}
    for r in runs:
        by_round.setdefault(r["round"], []).append(r["case"])
    assert all(sorted(cases) == ["A", "B", "C"] for cases in by_round.values())
    assert len({tuple(cases) for cases in by_round.values()}) > 1


def test_warmup_rows_stay_out_of_the_summary(out: Path) -> None:
    done = bench(out, "--case", f"A={OK}", "--rounds", "3", "--warmup", "2")
    assert done.returncode == 0, done.stderr
    assert [r["phase"] for r in rows(out)].count("warmup") == 2
    assert "| A | 3 | 0 |" in (out / "summary.md").read_text(encoding="utf-8")


def test_failing_case_is_invalid_not_fast(out: Path) -> None:
    done = bench(out, "--case", f"bad={FAIL}", "--rounds", "2", "--warmup", "0")
    assert done.returncode == 0, done.stderr
    assert {r["exit_code"] for r in rows(out)} == {"3"}
    assert "INVALID" in (out / "summary.md").read_text(encoding="utf-8")


def test_stderr_output_is_still_a_valid_run(out: Path) -> None:
    done = bench(out, "--case", f"warn={NOISY_STDERR}", "--rounds", "2", "--warmup", "0")
    assert done.returncode == 0, done.stderr
    assert {r["exit_code"] for r in rows(out)} == {"0"}


def test_refuses_an_existing_output_folder(out: Path) -> None:
    out.mkdir()
    (out / "runs.csv").write_text("keep me", encoding="utf-8")
    done = bench(out, "--case", f"A={OK}")
    assert done.returncode == 2 and "refusing to overwrite" in done.stderr
    assert (out / "runs.csv").read_text(encoding="utf-8") == "keep me"


def test_env_records_host_and_resolved_path(out: Path, tmp_path: Path) -> None:
    done = bench(out, "--case", f"A={OK}", "--rounds", "1", "--warmup", "0", "--path", str(tmp_path))
    assert done.returncode == 0, done.stderr
    env = json.loads((out / "env.json").read_text(encoding="utf-8"))
    assert env["host"]
    assert env["paths"][0]["exists"] is True
    if sys.platform == "win32":
        assert env["paths"][0]["filesystem"]
