# PR body rules

Applies to every PR body, whether or not `/draft-pr` is running. When the user corrects
a body, record the correction here.

## Reader

Write for a reader who is not on this machine. Keep what the diff and the repo explain:
what changed, why, and what was verified in a way they could repeat.

Leave out:
- lines only true of the author's machine — "not verified on this machine",
  deployed-home-directory state, backups taken locally
- verification that only restates the diff (e.g. "settings.json differs only by the
  new key", "chezmoi diff shows the new field present") — a reader with the diff open
  already sees this
- a check CI already runs on this PR (the test suite, lint) — CI's own status is the
  record of it, not the body
- checks of local state (`.trash`, `chezmoi status`, the session's skill list)
- commit signing state (signed or not) — signing is reconciled with the user in chat

A check any machine can repeat, such as "no duplicate `name:` across the skills", stays.
If something local still matters, tell the user in chat instead.

## Shape

- Title: a conventional commit, confirmed with the user before `gh pr create`.
- `## Summary` — one or two sentences.
- `## Changes` — one bullet per change, file paths in backticks.
- `## Verification` — only repeatable checks that aren't already covered by CI or
  obvious from the diff. Omit the heading when nothing survives that filter.
- `## Not in this PR` — what is deliberately left for later PRs. Omit when empty.
- Then the attribution lines from the session's system reminder.

## Process

- Always a draft PR.
- Push first with upstream set to the same-name remote branch. Ask before
  force-pushing.
- Write the body to a temp file, give its absolute path in chat, and wait for the
  user's review of the body before `gh pr create`. Delete the file afterwards.
