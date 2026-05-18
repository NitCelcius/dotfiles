---
name: draft-pr
description: Use when ready to open a draft PR — runs commit/lint/signature checks in parallel, then creates a draft PR with a generated title and body.
---

# Draft PR

Run pre-PR checks in parallel, report findings in one message, then create a draft PR.

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

**c) Signature**
```bash
git log --show-signature -1
```
If the latest commit is unsigned, ask:
> "The latest commit is unsigned. Do you want to sign it in your terminal before continuing, or skip signing?"

Note: Claude Code cannot connect to the Bitwarden SSH agent, so the user must
perform signing in their own terminal.

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
