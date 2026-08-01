## Skill: hear-my-plan

Invoke the `hear-my-plan` skill (via the Skill tool) before responding when either:
- The user runs `/hear-my-plan` explicitly, or
- The user's message is ~120+ words describing a plan, or contains the phrase "let's discuss"

This skill gates implementation: do not write code or edit files until the skill's confirmation step is cleared.

## Skill: measure-first

Invoke the `measure-first` skill before attempting a second fix for the same symptom.

## Tooling

- Run Python via `uv run python`, not `python3` directly
- Install Python packages via `uv add <pkg>` (CLI), not by editing `pyproject.toml` directly — exception: when a specific version constraint is needed, edit the file
- Use `git mv` for all file/directory moves to preserve history

## Environment

- OS: Windows 11
- Shell: bash and PowerShell are both available. Default to bash; use PowerShell for
  filesystem operations and for parsing external command output — bash mangles
  Windows paths and misreads Shift-JIS.
- PowerShell profile location: resolve with `echo $PROFILE`

## Git Conventions

### Ignore patterns
Use `.git/info/exclude` for local-only ignore patterns (e.g. worktree directories).
Do not add personal/local entries to `.gitignore`.

### Branch naming
- Bug fixes: `bugfix/(name-of-thing)` — preferred; `fix/` is acceptable
- Features: `feat/(name-of-something)`
- Append date as `YYMMDD` suffix only to avoid name conflicts, e.g. `feat/(name)/260328`
- WIP branches: prefix with `wip/`, e.g. `wip/bugfix/(name)`, `wip/feat/(name)`

### Commit messages
- Follow conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `chore:`, `style:`, `docs:`
- WIP commits: use `WIP: <plain description>`, e.g. `WIP: fix auth token expiry`
  - No conventional prefix needed — WIP commits are rebased and reworded before merging

### Session-start commit check
At the start of a session, run `git diff HEAD --shortstat` to gauge pending changes.
If the total insertions + deletions is roughly 300 or more, ask the user whether they want to commit before proceeding.

### Repo root
Before a git command that writes (`add`, `commit`, `checkout`, `reset`, `rebase`, `push`),
confirm the target with `git rev-parse --show-toplevel`. The working directory is often
not the repo you mean — the chezmoi source, worktrees, and Unity projects all sit
adjacent to or nested near each other.

### Merge strategy
Rebase & fast-forward merge. Not squash merge.
GitHub does not sign commits merged this way — the branch commits land on `main` as-is,
keeping their original signature state.

### SSH signing fallback
If the signing agent is unavailable mid-commit, retry with `--no-gpg-sign` immediately.
Do not ask, do not investigate the cause — an unsigned WIP commit is never worth
interrupting the work for.
When the task is done, state plainly that the commits were made without signing.
Because the merge is rebase & ff, unsigned commits stay unsigned on `main`. Signing is
therefore reconciled once, at PR time, not during the work — see the `draft-pr` skill.

## Communication & Clarifying Intent

  If the subject of my request is vague — the *what* (which component, file,
  repo, page, element) isn't explicitly named — stop and ask before acting.
  Don't guess the noun and run with it; a vague subject is the most common;
  cause of wrong-approach rework.
  When I describe a change, expect me to name the exact subject first. If I
  don't, prompt me for it rather than inferring.
  Surface ambiguity early and cheaply: one clarifying question up front beats
  a discarded attempt.

When reporting, lead with the current conclusion, the main evidence for it, and
the weakest assumption that would overturn it. Do not blur uncertainty; say
specifically what is still unverified.


## Before Editing

- Before changing logic that depends on data shapes, expected values, or canonical sources: read the actual source first, state the assumption explicitly, and wait for confirmation before editing.
- For refactors spanning more than ~5 files: lay out the commit plan (what changes, in what order, verification step per commit) before touching any file.
- If the same kind of transformation spans 3 or more files, do not hand-edit. Write a script and verify it with the diff.
- Do not drop an existing abstraction (dataclass, base class, config object) as part of an unrelated refactor. If removing it looks necessary, stop and ask.
- Before editing a file under `~`, check whether it is a deployed copy rather than the
  source: `chezmoi source-path <file>` prints the source and exits 0 when managed, and
  errors when not. Edit the source and apply. Editing the deployed copy works until the
  next `chezmoi apply` silently reverts it.

## Running Code

Never launch or poll a long-running process (servers, training runs, watch tasks) via a blocking tool call — output capture stalls verification. Detach it, write logs to a file, and tail the file if you need to check progress. If it cannot be detached, build the code and give the user the exact command to run.

## Reading Files

- Specify a range when calling Read unless the whole file is genuinely needed.
- For `docs/plans/*.md`, read the header block first, then pull in only the sections you need.
- Record what an image showed in text. Avoid re-reading the same image file; re-read only if it changed on disk.

## Searching

An empty result is not a finding. A search that returns nothing may have found absence,
or may have had a wrong path, a misremembered filename, or a pattern that could never
have matched.

Before reporting "there is no X", make the query prove it can return something: run it
against a term known to be present, or widen it one step and confirm the wider form
hits. Then report the absence, and say which check earned it.

## Claiming Done

Before saying a UI or runtime change works, assert it against the running application —
DevTools for web, Unity MCP for game work — and say which assertion you ran. "The tests
pass" and "the code looks right" are not substitutes when the gap in question is between
the code and the running app.

This does not apply to pure logic changes where a test genuinely is the observation. It
applies where the thing that could be broken is the integration: wiring, injection, event
binding, device and scene state.

The same holds for a subagent's report of its own work. An agent cannot observe what it
was structurally unable to see, so treat its summary as a claim and check it against an
artifact it did not author — the filesystem, the console, the running app.

If the assertion is cheap to keep, make it a regression test rather than discarding it.

## Code Review

When starting a review and no target (worktree, branch, or PR) is explicitly specified, ask for confirmation before proceeding.

## Subagents

- Dispatch a subagent when the work produces large output that main will not
  need to re-read (verification loops, log triage, cross-repo search).
- Keep it in the main session when the output will be referenced repeatedly.
- Default: return conclusions with file:line references, not raw content.
  Quote source only when the conclusion cannot stand without it.
- Read-only work (search, log triage, inventory) needs no confirmation.
- Before dispatching subagents that write code or edit files, main asks the user
  once, covering the whole batch. Within that batch a subagent executes without
  stopping to ask for routine permission.
- If a subagent hits a decision the batch approval did not cover, it surfaces it
  immediately — it does not guess and keep going, and it does not hold the
  question for its final report. A decision held is more expensive than a
  subagent that stops early, because work built on the wrong branch of it is
  thrown away.
- Delegate work whose result is cheap to verify. If checking the output costs about
  as much as producing it, do it in main instead. Claims a subagent cannot observe
  about itself — whether it was blocked, whether it waited — are never verifiable;
  do not build on them.
- Name the check before dispatching, not after: which artifact will show whether this
  worked, and what failure would look like in it. A check chosen after reading the
  report tends to be one the report already passes.
- On return, run that check against the artifact — filesystem, test output, the
  running app — not against the agent's summary. Proportion the check to the claim;
  one command is often enough. If a load-bearing claim has no checkable artifact,
  say so plainly rather than passing it through.
- Commits are always made by main.
