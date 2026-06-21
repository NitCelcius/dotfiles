## Skill: hear-my-plan

Invoke the `hear-my-plan` skill (via the Skill tool) before responding when either:
- The user runs `/hear-my-plan` explicitly, or
- The user's message is ~150+ words describing a plan, or contains the phrase "let's discuss"

This skill gates implementation: do not write code or edit files until the skill's confirmation step is cleared.

## Tooling

- Run Python via `uv run python`, not `python3` directly
- Use `git mv` for all file/directory moves to preserve history

## Environment

- OS: Windows 11
- Shell: bash (via Claude Code terminal)
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

### SSH signing fallback
If the signing agent socket is unavailable mid-commit, ask the user for confirmation, then retry with `--no-gpg-sign`.
The user will redo signing before merging.

## Communication & Clarifying Intent

  If the subject of my request is vague — the *what* (which component, file,
  repo, page, element) isn't explicitly named — stop and ask before acting.
  Don't guess the noun and run with it; a vague subject is the most common;
  cause of wrong-approach rework.
  When I describe a change, expect me to name the exact subject first. If I
  don't, prompt me for it rather than inferring.
  Surface ambiguity early and cheaply: one clarifying question up front beats
  a discarded attempt.


## Before Editing

- Before changing logic that depends on data shapes, expected values, or canonical sources: read the actual source first, state the assumption explicitly, and wait for confirmation before editing.
- For refactors spanning more than ~5 files: lay out the commit plan (what changes, in what order, verification step per commit) before touching any file.

## Running Code

Never launch or poll a long-running server (Gradio, dev servers, etc.) via tool calls — blocking output capture stalls verification. Build the code, then give the user the exact command to run it.

## Code Review

When starting a review and no target (worktree, branch, or PR) is explicitly specified, ask for confirmation before proceeding.

## Subagents

Parallel agents do not inherit tool permissions from the main session.
Prefer handling file edits and git operations directly rather than dispatching agents for them.
Agents are better suited for read-only research tasks.
