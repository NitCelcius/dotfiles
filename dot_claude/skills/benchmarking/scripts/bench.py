#!/usr/bin/env python3
"""Time commands in interleaved, shuffled rounds and write the results to a new folder.

Usage:
  uv run python bench.py --case A="cmd ..." --case B="cmd ..." --out DIR
                         [--rounds 10] [--warmup 1] [--prepare "cmd"] [--shell none]
                         [--path P ...] [--seed N] [--cwd DIR]

Each round runs every case once, in a fresh random order. `--warmup` rounds run first
and are recorded but left out of the summary. `--prepare` runs untimed before every
timed run (the cold-cache step). A run that exits non-zero is invalid, not fast.

`--shell none` splits the command itself and runs it directly; `pwsh`, `powershell`,
`bash` and `cmd` wrap it, adding that shell's start-up to every timing. stdout and
stderr are captured as bytes and never decoded, so a tool's stderr cannot break the run.

Writes into DIR, which must not exist yet:
  env.json    host, OS, Python, shell versions, and per --path the resolved location,
              drive, filesystem and `fsutil devdrv query` output (Windows)
  runs.csv    one row per run: round, position, case, phase, seconds, exit code
  summary.md  per case: valid runs, median, min, max, coefficient of variation, and a
              NOISY mark above NOISY_CV
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import json
import os
import platform
import random
import shlex
import socket
import statistics
import subprocess
import sys
import time
from pathlib import Path

NOISY_CV = 0.05
SHELL_PREFIX = {
    "pwsh": ["pwsh", "-NoProfile", "-Command"],
    "powershell": ["powershell", "-NoProfile", "-Command"],
    "bash": ["bash", "-c"],
    "cmd": ["cmd", "/d", "/c"],
}
SHELL_VERSION = {
    "pwsh": ["pwsh", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
    "powershell": ["powershell", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
    "bash": ["bash", "--version"],
}
PROBE_TIMEOUT_SECONDS = 15


def argv_for(command: str, shell: str) -> str | list[str]:
    if shell != "none":
        return [*SHELL_PREFIX[shell], command]
    if os.name == "nt":
        return command  # CreateProcess parses the command line itself
    return shlex.split(command)


def probe(args: list[str]) -> str:
    try:
        done = subprocess.run(args, capture_output=True, timeout=PROBE_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"unavailable: {error}"
    # Windows console tools such as fsutil print in the OEM code page (cp932 on Japanese).
    encoding = "oem" if os.name == "nt" and args[0] == "fsutil" else "utf-8"
    text = (done.stdout or done.stderr).decode(encoding, errors="replace").strip()
    return text.splitlines()[0] if text else f"exit {done.returncode}"


def filesystem_of(root: str) -> str | None:
    if os.name != "nt":
        return None
    name = ctypes.create_unicode_buffer(64)
    ok = ctypes.windll.kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root), None, 0, None, None, None, name, len(name)
    )
    return name.value if ok else None


def describe_path(path: str) -> dict:
    real = os.path.realpath(path)
    drive = os.path.splitdrive(real)[0]
    info = {"given": path, "resolved": real, "exists": os.path.exists(real), "drive": drive}
    if os.name == "nt" and drive:
        info["filesystem"] = filesystem_of(drive + "\\")
        info["devdrv_query"] = probe(["fsutil", "devdrv", "query", drive])
    return info


def environment(args: argparse.Namespace) -> dict:
    env = {
        "host": socket.gethostname(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "shell": args.shell,
        "cwd": os.path.realpath(args.cwd),
        "seed": args.seed,
        "rounds": args.rounds,
        "warmup": args.warmup,
        "prepare": args.prepare,
        "cases": dict(args.case),
        "paths": [describe_path(p) for p in args.path],
        "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if args.shell in SHELL_VERSION:
        env["shell_version"] = probe(SHELL_VERSION[args.shell])
    return env


def run_once(argv: str | list[str], cwd: str) -> tuple[float, int]:
    start = time.perf_counter_ns()
    try:
        done = subprocess.run(argv, cwd=cwd, capture_output=True)
        code = done.returncode
    except OSError:
        code = -1
    return (time.perf_counter_ns() - start) / 1e9, code


def summarise(rows: list[dict], cases: list[str]) -> str:
    lines = [
        "| case | valid | invalid | median s | min s | max s | CV | |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for case in cases:
        timed = [r for r in rows if r["case"] == case and r["phase"] == "timed"]
        valid = [r["seconds"] for r in timed if r["exit_code"] == 0]
        invalid = len(timed) - len(valid)
        if not valid:
            lines.append(f"| {case} | 0 | {invalid} | | | | | INVALID |")
            continue
        median = statistics.median(valid)
        cv = statistics.stdev(valid) / statistics.mean(valid) if len(valid) > 1 else 0.0
        mark = "NOISY" if cv > NOISY_CV else ""
        lines.append(
            f"| {case} | {len(valid)} | {invalid} | {median:.4f} | {min(valid):.4f} "
            f"| {max(valid):.4f} | {cv:.1%} | {mark} |"
        )
    return "\n".join(lines) + "\n"


def parse_case(text: str) -> tuple[str, str]:
    name, sep, command = text.partition("=")
    if not sep or not name or not command:
        raise argparse.ArgumentTypeError(f"expected NAME=COMMAND, got {text!r}")
    return name, command


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--case", type=parse_case, action="append", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--prepare")
    parser.add_argument("--shell", choices=["none", *SHELL_PREFIX], default="none")
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--cwd", default=".")
    args = parser.parse_args(argv)
    names = [name for name, _ in args.case]
    if len(set(names)) != len(names):
        parser.error("case names must be unique")
    if args.seed is None:
        args.seed = random.randrange(2**32)
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    out = Path(args.out)
    try:
        out.mkdir(parents=True)
    except FileExistsError:
        print(f"refusing to overwrite: {out} exists; pick a new folder", file=sys.stderr)
        return 2

    (out / "env.json").write_text(json.dumps(environment(args), indent=2), encoding="utf-8")
    cases = dict(args.case)
    rng = random.Random(args.seed)
    rows = []
    phases = ["warmup"] * args.warmup + ["timed"] * args.rounds
    for round_no, phase in enumerate(phases, start=1):
        order = list(cases)
        rng.shuffle(order)
        for position, name in enumerate(order, start=1):
            if args.prepare:
                run_once(argv_for(args.prepare, args.shell), args.cwd)
            seconds, code = run_once(argv_for(cases[name], args.shell), args.cwd)
            rows.append({
                "round": round_no, "position": position, "case": name,
                "phase": phase, "seconds": seconds, "exit_code": code,
            })

    with (out / "runs.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = summarise(rows, list(cases))
    (out / "summary.md").write_text(summary, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
