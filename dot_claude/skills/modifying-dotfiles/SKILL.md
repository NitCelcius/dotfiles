---
name: modifying-dotfiles
description: Use when changing any config managed by the dotfiles chezmoi source (Claude Code settings, skills, hooks, Zed, git, shell), or when asked to log or reconcile why dotfiles changed.
---

# Modifying dotfiles

The dotfiles repo is public and chezmoi-managed, so three things go wrong: an edit lands
on the wrong copy of a config, private or machine-local detail reaches the repo, and the
reason for a change is lost. Follow the steps in order. Step 1 comes before any edit.

## 1. Branch first

Never change dotfiles on main. One feature per branch, one draft PR each. Name the branch
per `git-workflow`; if the main checkout holds other work, use `using-git-worktrees`.
Run `git rev-parse --show-toplevel` and confirm it is the branch's checkout before any
write. Staging follows `commit-scope-audit`.

## 2. Identify which config

Run `chezmoi source-path <file>` on the config in question. It prints the source to edit;
never edit the deployed copy. It exits non-zero for a file chezmoi does not manage, so
stop and ask which config is meant rather than guessing.

A `modify_` template (partial management) has a carry-over list of live keys it keeps.
Read its header and that list before editing, since anything not on it is overwritten on
every apply. `chezmoi source-path` does not resolve these; find `modify_<basename>` next
to the target's source directory. The apply-side check belongs to `chezmoi-sync`.

## 3. Public-repo rules

- Never commit machine-specific config (Zed `ssh_connections`, WSL settings) or
  private/lab-related files and skills. Keep machine-local keys in `modify_` templates so
  the live value survives an apply.
- Write no private detail (paths, hostnames, file names, credentials, personal data) in a
  commit message or file.
- Before apply, list open PRs (`gh pr list`) that touch the same files and leave those
  files out of the apply.
- If `chezmoi status` hangs on Bitwarden, fall back to `chezmoi diff -- <target>` per
  file, each under a timeout.

## 4. Verification

Run the commands in the dotfiles `CLAUDE.md` `## Verification` block: `quick` at
close-out, `full` before a commit or PR.

## 5. Log the why after the commit

Draft one row for the Notion DB "設定変更ログ" and show it before writing. Property names,
options, and the call shape are in `schema.md`; copy them verbatim.

- Fields: 日付 (commit date), 対象, 変更 (one line, the what), 理由 (the why), 確度,
  リンク (commit SHA URL, also the dedupe key).
- 確度 is 確定 only when the user stated the reason or the session made it explicit. A
  reason inferred from a commit body or diff is 推定. If unknown, 理由 is 不明 and 確度 is
  不明. Never write a guess as 確定.
- If the reason is missing, ask once for it, in the same message that shows the draft.
- Before creating, query the data source for a row with the same リンク and skip if found.
- After writing the row, or when the user skips it, run
  `python ~/.claude/dotfiles-change-log/dotfiles_change_log.py mark <sha>` so the
  SessionStart count of unlogged commits stays right. After a reconcile, mark the newest
  commit handled.
- Japanese text follows the Content rules in `save-to-knowledge/SKILL.md`.

### Reconcile mode

For commits with no row (changed in another session, or by hand): list the commits in the
dotfiles repo, check each SHA URL against the DB, and draft rows for the missing ones as
推定 or 不明. Show the list, write on approval, then let the user fill the 不明 rows in one
pass and update those rows.
