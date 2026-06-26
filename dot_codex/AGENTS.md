# Personal Codex Guidance

Imported and adapted from `~/.claude/CLAUDE.md` on 2026-06-26.

## Planning and Discussion

- If the user runs `/hear-my-plan`, sends a long plan for discussion, or says "let's discuss", treat it as a planning request. Discuss and confirm direction before editing files.

## Tooling

- Run Python via `uv run python` when working in projects that use `uv`.
- Use `git mv` for file and directory moves so history is preserved.

## Environment

- OS: Windows 11.
- Prefer commands that work in the active shell. In Codex CLI sessions this is often PowerShell; in Claude Code it may be bash.
- PowerShell profile location can be resolved with `echo $PROFILE`.

## Git Conventions

### Ignore Patterns

- Use `.git/info/exclude` for local-only ignore patterns, such as worktree directories.
- Do not add personal or local entries to `.gitignore`.

### Branch Naming

- Bug fixes: `bugfix/(name-of-thing)` is preferred; `fix/` is acceptable.
- Features: `feat/(name-of-something)`.
- Append a `YYMMDD` date suffix only to avoid name conflicts, for example `feat/(name)/260328`.
- WIP branches: prefix with `wip/`, for example `wip/bugfix/(name)` or `wip/feat/(name)`.

### Commit Messages

- Follow conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `chore:`, `style:`, `docs:`.
- WIP commits: use `WIP: <plain description>`, for example `WIP: fix auth token expiry`.
- WIP commits do not need a conventional prefix because they are rebased and reworded before merging.

### Session-Start Commit Check

- At the start of a coding session, run `git diff HEAD --shortstat` to gauge pending changes.
- If insertions plus deletions are roughly 300 or more, ask whether the user wants to commit before proceeding.

### SSH Signing Fallback

- If the signing agent socket is unavailable during a commit, ask for confirmation, then retry with `--no-gpg-sign`.
- The user will redo signing before merging.

## Communication and Clarifying Intent

- If the subject of a request is vague, ask before acting. Do not guess which component, file, repo, page, or element the user means.
- Surface ambiguity early with one concise clarifying question.

## Before Editing

- Before changing logic that depends on data shapes, expected values, or canonical sources, read the actual source first and state the assumption explicitly before editing when confirmation is needed.
- For refactors spanning more than about five files, lay out the commit plan, change order, and verification step per commit before touching files.

## Running Code

- Do not launch or poll long-running servers through tool calls unless the user explicitly wants that workflow. Prefer building or validating, then provide the exact command when a persistent server should be run by the user.

## Code Review

- When starting a review and no target is specified, ask which target to review before proceeding.

## Subagents

- Prefer handling file edits and git operations directly.
- Use agents primarily for read-only research tasks.
