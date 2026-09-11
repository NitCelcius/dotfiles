"""Drive verify_on_stop.py end to end against a throwaway git repo.

Run: python test_verify_on_stop.py

The parser fixtures live in the hook itself (`--selftest`). This file covers what
they cannot: that the guard really skips an unchanged tree, notices an edit to an
untracked file, blocks once on a failure, and never blocks twice in a row. The
first two were real bugs caught here before the hook was wired into settings.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "verify_on_stop.py"

BLOCK = """# CLAUDE.md

## Verification

- **quick** (task close-out, aim for under 30s): `{cmd}`
- **full** (before a commit or PR): `{cmd}`
- **Out of scope**: nothing
"""

results: list[tuple[bool, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((ok, name, detail))


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


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="verifyhook-"))
    repo = tmp / "repo"
    data_root = tmp / "state"
    repo.mkdir()
    marker = repo / "ran.log"

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    git("config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "seed")

    r = fire(repo, data_root)
    check("no CLAUDE.md -> allows stop", r.returncode == 0, f"rc={r.returncode} {r.stderr[:120]}")

    (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n## Commands\n\n- `npm test`\n", encoding="utf-8")
    r = fire(repo, data_root)
    check("no Verification block -> allows stop", r.returncode == 0, f"rc={r.returncode}")

    passing = f"python -c \"open(r'{marker}','a').write('x')\""
    (repo / "CLAUDE.md").write_text(BLOCK.format(cmd=passing), encoding="utf-8")
    r = fire(repo, data_root)
    check("passing quick -> allows stop", r.returncode == 0, f"rc={r.returncode} {r.stderr[:200]}")
    check(
        "passing quick actually executed the command",
        marker.exists() and marker.read_text().count("x") == 1,
        f"marker={marker.read_text() if marker.exists() else '<missing>'!r}",
    )

    r = fire(repo, data_root)
    check("unchanged tree -> allows stop", r.returncode == 0, f"rc={r.returncode}")
    check(
        "unchanged tree -> skipped re-running",
        marker.read_text().count("x") == 1,
        f"marker={marker.read_text()!r}",
    )

    (repo / "seed.txt").write_text("seed changed\n", encoding="utf-8")
    r = fire(repo, data_root)
    check(
        "tracked edit -> ran again",
        marker.read_text().count("x") == 2,
        f"marker={marker.read_text()!r}",
    )

    # CLAUDE.md is untracked here on purpose: editing an untracked file must
    # still invalidate the cached pass, or a new module never gets verified.
    (repo / "CLAUDE.md").write_text(
        BLOCK.format(cmd="python -c \"import sys; print('boom detail'); sys.exit(3)\""),
        encoding="utf-8",
    )
    r = fire(repo, data_root)
    check("untracked edit -> not skipped, and blocks (exit 2)", r.returncode == 2, f"rc={r.returncode}")
    check("failure output reaches stderr", "boom detail" in r.stderr, f"stderr={r.stderr[:300]!r}")

    r = fire(repo, data_root)
    check("same failing state twice -> allows stop", r.returncode == 0, f"rc={r.returncode}")

    (repo / "seed.txt").write_text("seed changed again\n", encoding="utf-8")
    r = fire(repo, data_root, stop_hook_active=True)
    check("stop_hook_active -> allows stop", r.returncode == 0, f"rc={r.returncode}")

    bare = tmp / "notrepo"
    bare.mkdir()
    (bare / "CLAUDE.md").write_text(BLOCK.format(cmd="exit 1"), encoding="utf-8")
    r = fire(bare, data_root)
    check("not a git repo -> allows stop", r.returncode == 0, f"rc={r.returncode}")

    failed = 0
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failed += 1
            print(f"      {detail}")
    print(f"\n{len(results) - failed}/{len(results)} passed")
    shutil.rmtree(tmp, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
