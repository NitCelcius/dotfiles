---
name: draft-pr
description: Use when ready to open a draft PR — runs commit log, lint, and signature checks in parallel, then creates a draft PR with a generated title and body.
---

# Draft PR

Run pre-PR checks in parallel, report findings in one message, then create a draft PR.

Unsigned commits mid-work are expected — the signing agent drops out often and the
work does not stop for it. But the merge is rebase & fast-forward, so GitHub does
not sign anything on the way in: whatever is unsigned here stays unsigned on `main`.

PR time is therefore the one place signing gets reconciled. Report unsigned commits
here — once, as a single line with the count — and offer to re-sign. Do not treat it
as a blocker, and do not ask again if the user declines.

## Flow

```
checks (parallel) → report or skip → write .git/pr-body.md → confirm title → gh pr create --draft → cleanup
```

## Step 1: Parallel Checks

**a) Commit log**
```bash
git log main..HEAD --oneline
```
Flag only: WIP commits or clearly incomplete messages. Commit count alone is not a problem.

**b) Lint**

Detect lint script without reading the full file:

- Windows (PowerShell):
```powershell
(Get-Content package.json | ConvertFrom-Json).scripts.PSObject.Properties |
  Where-Object { $_.Name -match 'lint' } |
  ForEach-Object { "$($_.Name): $($_.Value)" }
```

- Linux/Mac:
```bash
# prefer jq if available, otherwise node
jq -r '.scripts | to_entries[] | select(.key | test("lint")) | "\(.key): \(.value)"' package.json 2>/dev/null ||
  node -e "const s=require('./package.json').scripts||{}; Object.keys(s).filter(k=>/lint/i.test(k)).forEach(k=>console.log(k+': '+s[k]))"
```

If a lint script is found, run it. Report errors with fix suggestions. If no `package.json` or no lint script, skip silently.

**c) Signature count**
```bash
git log main..HEAD --pretty=%G? | grep -c '^N' || true
```
Report as one line: `N of M commits unsigned — re-sign before merge?` Since the merge
is rebase & ff, GitHub will not sign these on the way in.

To re-sign the whole branch in one pass, if the user wants it:
```bash
git rebase --exec 'git commit --amend --no-edit -S' main
```
This requires a working signing agent in the user's own terminal. If it is still down,
say so once and continue — this never blocks the PR.

## Step 2: Report or Skip

- All clean → proceed silently to Step 3
- Any findings → report everything in **one message**, wait for user before continuing

## Step 3: Generate PR Draft

Generate title and body from `git log main..HEAD` and `git diff main..HEAD`.

Write body to `.git/pr-body.md`:
```bash
# (not tracked by git)
```

Propose title as a single line for user to confirm or edit.

## Step 4: Create Draft PR

After user confirms title:
```bash
gh pr create --draft --title "<confirmed title>" --body-file .git/pr-body.md
```

Then delete the temp file:
```bash
# Windows
Remove-Item .git/pr-body.md

# Linux/Mac
rm .git/pr-body.md
```
