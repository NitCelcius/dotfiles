# Usage scan: instructions for a Claude session on another machine

Goal: count which skills and slash commands this machine's Claude Code sessions used,
so the counts from every machine can be merged before deciding which skills to remove.
Read-only on this machine: no commits, no pushes, no edits outside the output folder.

1. `git fetch origin` in the dotfiles checkout, then run the script from the
   `feat/usage-scan` branch without switching the main checkout:
   `git worktree add .worktree/feat-usage-scan origin/feat/usage-scan` (detached is fine).
2. Run: `uv run python .worktree/feat-usage-scan/tools/usage-scan/transcript_scan.py ~/.claude/projects <out>`,
   where `<out>` is a temp folder outside any repo.
   Expected: one line listing `<host>-sessions.csv`, `<host>-skills.csv` and `<host>-summary.md`.
3. Check `cleanupPeriodDays` in `~/.claude/settings.json` and note the date of the oldest
   session in `<host>-sessions.csv`: counts only cover what is still on disk.
4. Create a Notion page under "Claude Code の usage report" titled
   `usage scan <host> <date>`. Paste the full contents of `<host>-skills.csv` as a code
   block, then the oldest session date and `cleanupPeriodDays`. Do not upload
   `<host>-sessions.csv`; it stays local.
5. Remove the worktree: `git worktree remove .worktree/feat-usage-scan`.
