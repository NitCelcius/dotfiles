---
name: benchmarking
description: Use when measuring command duration or comparing performance before and after a change, including shell profiles, hooks, linters, and builds. Define the workload and conditions, then use hyperfine to measure it. Not for finding a bug's cause; that is measure-first.
---

# Benchmarking

Use [hyperfine](https://github.com/sharkdp/hyperfine) for timing and statistics.
The small `scripts/bench.py` wrapper records the invocation and saves results in a
new directory. Its usefulness is still being evaluated; do not add a custom timing
loop, randomized interleaving, or a benchmark configuration format for a one-off run.

## 1. Define the comparison before running it

Record the question, before/after revisions, and the smallest difference that would
change a decision (milliseconds or percent). Then specify:

- **Workload and boundary:** the exact commands, files or hook payload, expected
  exit code/output, and whether interpreter startup and any wrapper are included.
- **Fixed conditions:** working directory, tool executable/version, environment
  overrides, and the same input data. Use explicit before/after script or config
  paths; changing worktrees alone does not change an installed profile or hook.
- **State:** which caches or generated files persist, and which are reset before
  each run. Isolate hook state from the real user's state and from the other case.

Check each command once with visible output and the intended input. Confirm that it
performs the intended work, including the hook branch or cache path being compared.
Exit 0 alone does not establish that a hook actually did anything. Restore any state
changed by this check before measuring.

Record drive/filesystem or Defender details when they are relevant to the question;
do not require an elevated disk audit for every profile or hook comparison. If a
condition differs, state it alongside the result.

## 2. Choose warmup and cache handling

`--warmup N` is optional; start with 1 for repeated use, or omit it for a first-use
scenario with its state reset before every run. A fresh process is started for every
sample. Prior warmup processes do not preserve that process's in-memory state.

Distinguish OS file caches from application caches. For example, compare a hook's
cache-hit and cache-miss paths separately. A warmup may populate the hook's result
cache and turn all timed runs into skips. Use `--prepare` to reset the specific
state under test before each warmup and measured run, or seed a repeatable cache hit.
Preparation must fail if it cannot establish that state; hyperfine aborts on failure.

Neither `--warmup 0` nor a new temp directory guarantees cold OS caches. Describe
uncontrolled cache state as uncontrolled, rather than claiming cold or warm.

## 3. Run

Requires Python/uv and hyperfine on PATH (verified with hyperfine 1.20.0).
Follow the [official installation instructions](https://github.com/sharkdp/hyperfine#installation)
if it is missing. Check `hyperfine --version` and the measured tool's version first.

PowerShell example, measuring interpreter startup plus execution of each profile:

```powershell
uv run python ~/.claude/skills/benchmarking/scripts/bench.py --out ./results/profile-01 -- --shell=none --runs 10 --warmup 1 --command-name before 'pwsh -NoProfile -File ./before/profile.ps1' --command-name after 'pwsh -NoProfile -File ./after/profile.ps1'
```

`--shell=none` executes the command directly. Select `pwsh` or `powershell` explicitly
inside the measured command and keep its executable/version fixed between cases.
They are separate runtimes; measuring both is only needed if both are in scope.
`-NoProfile` avoids loading the installed profile before the selected script. This
example measures standalone script execution, not time to an interactive prompt.
For profiles that depend on dot-sourcing or host behavior, use a scenario script that
reproduces that behavior and record its timing boundary.

For commands needing shell syntax, pass hyperfine's `--shell` option. Hyperfine
calibrates and subtracts the intermediary shell's overhead; do not mistake that for
shell-startup timing. To measure startup, keep `--shell=none` and put the shell itself
in the command. Paths containing spaces inside a command need their own quotes.

Hook example, with the same JSON input reopened for every invocation:

```powershell
uv run python ~/.claude/skills/benchmarking/scripts/bench.py --out ./results/hook-01 --cwd ./fixture -- --shell=none --runs 10 --warmup 1 --input payload.json --command-name before 'python before/hook.py' --command-name after 'python after/hook.py'
```

Use `--input FILE`; piping a payload into the benchmark driver does not replay it
for each run. Inputs, commands, and prepare paths are relative to `--cwd`; `--out`
is relative to the caller. If a command invokes `uv run`, its startup and environment
handling are part of the measurement too.

For a hook expected to block with exit 2, save this scenario adapter as `check_block.py`:

```python
# check_block.py: replay hook input and require the blocking exit code.
# Args: hook program and arguments. Input: JSON on stdin. Exit: 0 only for exit 2.
import subprocess
import sys

done = subprocess.run(sys.argv[1:], input=sys.stdin.buffer.read())
if done.returncode != 2:
    print(f"expected hook exit 2, got {done.returncode}", file=sys.stderr)
    sys.exit(1)
```

Use commands such as `'python check_block.py python before/hook.py'` with the same
`--input` option. The adapter's startup, input forwarding, and validation are timed;
use it for both cases. Add scenario-specific output checks when exit status alone
cannot distinguish the intended work. Do not use `--ignore-failure` to hide unexpected
results. Debug failing commands with visible output before rerunning the comparison.

## 4. Preserve and interpret the result

Everything after `--` goes to hyperfine, except that the wrapper owns
`--export-json` and `--export-markdown`. It adds no warmup, shell, or repetition
defaults. Start with 10 measured runs; use fewer only for a functional smoke check.

`--out` must not exist. It receives:

- `run.json`: exact argv, cwd, platform, hyperfine version, timestamps, and exit code.
- `results.json`: hyperfine statistics and individual timing samples.
- `summary.md`: hyperfine's comparison table.
- `stdout.log` and `stderr.log`: the driver's output, preserved as bytes.

The wrapper does not inventory the measured tools, revisions, fixtures, environment
variables, or disk state; keep the conditions from step 1 with the report. Driver
logs do not capture suppressed target output. A nonzero wrapper exit (or a null
exit code after interruption) means the run is incomplete or failed; partial files
are diagnostic evidence, not an accepted comparison. Keep results outside tracked
files and remove only artifacts created by the experiment.

Cases run sequentially, not in randomized interleaved rounds. If ordering or drift
could change the decision, repeat with reversed order in a new result directory.
An unstable difference is inconclusive; do not add a new runner just to resolve it.

Report the question and conditions, timing boundary, table, absolute/relative
difference, spread and warnings, and whether the difference changes the decision.
A fixed CV threshold is not a pass/fail rule. This experiment establishes timing
under the recorded conditions, not general performance or the usefulness of the
workflow. After using it on a real change, note the extra setup and manual corrections
before deciding which parts are worth keeping.
