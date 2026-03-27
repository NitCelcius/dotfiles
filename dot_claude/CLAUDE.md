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
