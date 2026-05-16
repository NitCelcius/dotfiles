## Skill: hear-my-plan

Invoke the `hear-my-plan` skill (via the Skill tool) before responding when either:
- The user runs `/hear-my-plan` explicitly, or
- The user's message is ~150+ words describing a plan, or contains the phrase "let's discuss"

This skill gates implementation: do not write code or edit files until the skill's confirmation step is cleared.

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
