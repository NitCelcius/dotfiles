"""Drive transcript_scan.py's session-start mode against a throwaway home directory.

Run: uv run --with pytest pytest dot_claude/usage-scan

Covers the hook's contract: it scans when no report exists or the newest CSV is 7 or
more days old, skips otherwise, and never writes to stdout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "transcript_scan.py"
DAY_SECONDS = 24 * 60 * 60


@pytest.fixture
def home(tmp_path: Path) -> Path:
    project = tmp_path / ".claude" / "projects" / "demo"
    project.mkdir(parents=True)
    records = [
        {"type": "user", "timestamp": "2026-10-01T00:00:00Z", "message": {"content": "hello"}},
        {
            "type": "assistant",
            "timestamp": "2026-10-01T00:01:00Z",
            "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "draft-pr"}}]},
        },
    ]
    (project / "s1.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return tmp_path


def out_dir(home: Path) -> Path:
    return home / ".claude" / "usage-scan" / "out"


def fire(home: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), "session-start"],
        input="{}",
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )


def test_first_run_writes_reports_silently(home: Path) -> None:
    done = fire(home)
    assert done.stdout == ""
    assert len(list(out_dir(home).glob("*-skills.csv"))) == 1
    assert "draft-pr" in next(out_dir(home).glob("*-skills.csv")).read_text(encoding="utf-8")


def test_fresh_report_is_left_alone(home: Path) -> None:
    fire(home)
    csv = next(out_dir(home).glob("*-skills.csv"))
    csv.write_text("sentinel\n", encoding="utf-8")
    done = fire(home)
    assert done.stdout == ""
    assert csv.read_text(encoding="utf-8") == "sentinel\n"


def test_week_old_report_is_rescanned(home: Path) -> None:
    fire(home)
    week_ago = time.time() - 7 * DAY_SECONDS - 60
    for csv in out_dir(home).glob("*.csv"):
        csv.write_text("sentinel\n", encoding="utf-8")
        os.utime(csv, (week_ago, week_ago))
    done = fire(home)
    assert done.stdout == ""
    assert "draft-pr" in next(out_dir(home).glob("*-skills.csv")).read_text(encoding="utf-8")


def test_missing_projects_dir_is_silent(tmp_path: Path) -> None:
    done = fire(tmp_path)
    assert done.stdout == ""
    assert not out_dir(tmp_path).exists()
