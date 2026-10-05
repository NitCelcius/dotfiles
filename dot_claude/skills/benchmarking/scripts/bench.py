#!/usr/bin/env python3
"""Run hyperfine and save its results, invocation, and logs in a new directory.

Usage: uv run python bench.py --out DIR [--cwd DIR] -- HYPERFINE_ARGS...
Requires hyperfine on PATH. Timing, repetition, and statistics belong to hyperfine.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="new results directory, relative to the caller")
    parser.add_argument("--cwd", default=".", help="working directory for hyperfine and its commands")
    parser.add_argument("hyperfine_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    forwarded = args.hyperfine_args
    if forwarded[:1] == ["--"]:
        forwarded = forwarded[1:]
    if not forwarded:
        parser.error("pass hyperfine arguments and commands after --")
    if any(a.split("=", 1)[0] in {"--export-json", "--export-markdown"} for a in forwarded):
        parser.error("--out manages the JSON and Markdown exports")
    cwd = Path(args.cwd).resolve()
    if not cwd.is_dir():
        parser.error(f"working directory does not exist: {cwd}")
    executable = shutil.which("hyperfine")
    if executable is None:
        parser.error("hyperfine is required on PATH; see https://github.com/sharkdp/hyperfine#installation")
    try:
        version = subprocess.run([executable, "--version"], capture_output=True, check=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as error:
        parser.error(f"cannot run hyperfine: {error}")
    out = Path(args.out).resolve()
    try:
        out.mkdir(parents=True)
    except OSError as error:
        parser.error(f"cannot create new results directory {out}: {error}")
    command = [executable, "--export-json", str(out / "results.json"),
               "--export-markdown", str(out / "summary.md"), *forwarded]
    record = {
        "started": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "hyperfine_version": version.stdout.decode("utf-8", errors="replace").strip(),
        "cwd": str(cwd),
        "argv": command,
        "exit_code": None,
    }
    manifest = out / "run.json"
    manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    try:
        done = subprocess.run(command, cwd=cwd, capture_output=True)
        code, stdout, stderr = done.returncode, done.stdout, done.stderr
    except OSError as error:
        code, stdout, stderr = 1, b"", str(error).encode("utf-8")
    except KeyboardInterrupt:
        code, stdout, stderr = 130, b"", b"interrupted; results may be incomplete\n"
    (out / "stdout.log").write_bytes(stdout)
    (out / "stderr.log").write_bytes(stderr)
    if code == 0:
        try:
            results = json.loads((out / "results.json").read_text(encoding="utf-8"))["results"]
            if not results or not all(r.get("times") for r in results) or not (out / "summary.md").stat().st_size:
                raise ValueError("missing timing samples or summary")
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            code = 1
            print(f"incomplete hyperfine results: {error}", file=sys.stderr)
    record.update(exit_code=code, finished=datetime.now(timezone.utc).isoformat())
    manifest.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(stdout.decode("utf-8", errors="replace"), end="")
    print(stderr.decode("utf-8", errors="replace"), end="", file=sys.stderr)
    print(f"Results: {out}")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
