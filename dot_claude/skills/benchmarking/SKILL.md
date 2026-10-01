---
name: benchmarking
description: Use when measuring or comparing performance — how long a command, build, install, test run or file operation takes, or whether a drive, filesystem, machine or config change makes it faster. Not for narrowing the cause of a bug; that is measure-first.
---

# Benchmarking

A timing is only as good as what it held constant. Past runs here went wrong by
comparing ReFS with NTFS as if only the filesystem differed, by not knowing which drive
held each artifact, by letting a tool's stderr crash PowerShell, by running all of A
and then all of B, by mixing cold and warm caches, and by overwriting a tracked result
file. Follow the steps in order.

## 1. Write the question first

Before running anything, write down: the question, the one variable being compared,
and what result would change a decision. Everything else stays the same between cases.
If something else cannot be held equal (different disk, partition vs VHD, Defender
mode, another machine), say in the report that the comparison is not like-for-like.

## 2. Record the environment

For every path the cases touch, resolve where it really is: follow junctions and
symlinks (`Get-Item <path> | Select-Object Target`, or `os.path.realpath`), then record
the drive, filesystem, and for a Dev Drive its trust and filters
(`fsutil devdrv query X:`, which needs an elevated shell). Also record the host name,
OS, tool versions and PowerShell version. Results from several machines are only
comparable when the host is the variable under test; keep each host's record with
its results.

The harness writes all of this to `env.json` (host, OS, Python, shell, and each
`--path`); add by hand anything it cannot see, such as Defender mode.

## 3. Choose cold or warm, once per experiment

- **Warm:** run warmup rounds and discard them (`--warmup`).
- **Cold:** run a prepare step before every timed run (`--prepare`) that resets the
  cache under test: a fresh clone, a cleared tool cache, a new temp directory. If a
  true cold start cannot be guaranteed (the OS file cache usually cannot be dropped
  without admin tools), call the experiment warm.

Never mix the two in one comparison.

## 4. Run with the harness

```
uv run python ~/.claude/skills/benchmarking/scripts/bench.py \
  --case A="<command>" --case B="<command>" \
  --rounds 10 --warmup 1 --path <dir> --out <new results dir>
```

It interleaves the cases: every round runs each case once, in a fresh random order
(the seed is in `env.json`). It captures stderr as bytes and judges a run only by its
exit code, so a non-zero exit is an invalid run, never a fast one. `--shell none`
(default) runs the command directly; `--shell pwsh|powershell|bash|cmd` wraps it and
adds that shell's start-up to every timing, so use the same shell for all cases.

Without the harness, keep the same rules: interleave rounds, check exit codes, and
time from Python or PowerShell 7 rather than Windows PowerShell 5.1.

### PowerShell and native stderr

Checked on 5.1.26100 and 7.6.6: in 5.1 with `$ErrorActionPreference = 'Stop'`, a native
command whose stderr is redirected (`2>&1` or `2>$null`) throws on its first stderr
line even when it exits 0. 7.x does not throw unless
`$PSNativeCommandUseErrorActionPreference = $true` and the exit code is non-zero. 5.1
also drops double quotes embedded in native arguments. Judge a native command by
`$LASTEXITCODE`, never by whether it wrote to stderr.

## 5. Check the result is valid

- At least 10 timed rounds. Report median, min and max, not a single run or the mean.
- A case with a coefficient of variation above 5% is marked NOISY in `summary.md`.
  Do not draw a conclusion from it: find the noise source (background work, thermal,
  Defender scan, another process on the disk) and rerun.
- Any invalid run means the case did not do the intended work; fix that first.
- When the difference matters, watch what limits the run while it happens (CPU, disk,
  one busy core, Defender) with Task Manager or `Get-Counter`, and name it in the
  report.

## 6. Keep results, never overwrite

`--out` must be a new folder; the harness refuses an existing one. Put results outside
tracked files, or in a new timestamped file if they belong in a repo. Run `git status`
afterwards and restore anything the run changed.

## 7. Report

The question; an environment table (host, paths with drive and filesystem, versions);
the method (cold or warm, rounds, interleaved order, shell); the `summary.md` table;
the verdict, stated with how large the difference is against the spread; what limited
the run; and what was not held equal.
