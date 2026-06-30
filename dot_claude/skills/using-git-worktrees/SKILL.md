---
name: using-git-worktrees
description: Use when starting feature or bugfix work that needs isolation - suggests branch name following repo convention, confirms with user, then creates isolated git worktree with proper gitignore handling
---

# Using Git Worktrees

## Overview

Git worktrees create isolated workspaces sharing the same repository, allowing work on multiple branches simultaneously without switching.

**Core principle:** Detect work intent → suggest branch name following convention → confirm with user → create isolated workspace with safety verification.

**Announce at start:** "I'm using the using-git-worktrees skill to set up an isolated workspace."

## Step 1: Detect Work Description

If user provided context (e.g., "/using-git-worktrees, implement login feature"):
- Extract the work description: "implement login feature"

If NO context provided:
```
What are you implementing? (e.g., "login feature", "fix auth token issue", "stage-2-1")
```

Wait for user response. Use this to inform branch name suggestion.

## Step 2: Detect Repo Naming Convention

Check CLAUDE.md for explicit convention:

```bash
grep -A 5 "Branch naming" CLAUDE.md 2>/dev/null | head -10
```

Look for patterns like:
- `feat/` vs `feature/`
- `bugfix/` vs `fix/`
- `wip/` prefix
- Date suffix `YYMMDD`

If CLAUDE.md doesn't specify, examine recent branches:

```bash
git branch -r --sort=-committerdate | head -5
```

## Step 3: Suggest and Confirm Branch Name

Based on work description + detected convention, suggest a branch name.

**Examples:**
- Work: "implement login feature" + convention `feat/` → Suggest: `feat/login`
- Work: "fix auth token expiry" + convention `bugfix/` → Suggest: `bugfix/auth-token-expiry`
- Work: "stage-2-1" + convention with date suffix → Suggest: `feat/stage-2-1/260607`

**Use `AskUserQuestion` to confirm.** Always include the suggested name as the first option and "Other" will be provided automatically for a custom name:

```
AskUserQuestion({
  questions: [{
    question: "Which branch name should we use?",
    header: "Branch name",
    options: [
      { label: "feat/login", description: "Suggested — follows feat/ convention (Recommended)" },
      { label: "feat/login/260607", description: "Same with date suffix to avoid conflicts" },
    ]
  }]
})
```

- If user picks an option: use it as-is
- If user picks "Other" and types a custom name: use their input, validate against detected convention

**If convention unclear:** Use `AskUserQuestion` to ask which prefix to use before suggesting.

## Step 4: Directory Setup

Use `.worktree/` (singular) as the project-local directory:

```bash
WORKTREE_DIR=".worktree"
WORKTREE_PATH="${WORKTREE_DIR}/${BRANCH_NAME}"
```

## Step 5: Safety Verification - Gitignore Check

**MUST verify directory is ignored before creating worktree:**

```bash
git check-ignore -q .worktree 2>/dev/null
if [ $? -ne 0 ]; then
  # Not ignored, add to local gitignore
  mkdir -p .git/info
  echo ".worktree/" >> .git/info/exclude
  echo "Added .worktree/ to .git/info/exclude"
fi
```

**Why critical:** Prevents accidentally committing worktree contents to repository.

**Use `.git/info/exclude` NOT `.gitignore`:**
- `.git/info/exclude` is local-only (not committed)
- `.gitignore` is for project-wide conventions
- Tooling directories should use local ignore

## Step 6: Create Worktree

```bash
WORKTREE_PATH=".worktree/${BRANCH_NAME}"
git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME"
cd "$WORKTREE_PATH"
```

## Step 7: Run Project Setup

Auto-detect and run appropriate setup:

```bash
# Node.js
if [ -f package.json ]; then pnpm install; fi

# Rust
if [ -f Cargo.toml ]; then cargo build; fi

# Python
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then uv run python -m pip install -r requirements.txt; fi

# Go
if [ -f go.mod ]; then go mod download; fi
```

## Step 8: Verify Clean Baseline

Run tests to ensure worktree starts clean:

```bash
# Examples - use project-appropriate command
pnpm test     # Node.js
cargo test    # Rust
pytest        # Python
go test ./... # Go
```

**If tests fail:** Report failures, ask whether to proceed or investigate.

**If tests pass:** Report ready.

## Step 9: Report Location and Status

```
Worktree ready at .worktree/<branch-name>
Tests passing (<N> tests, 0 failures)
Ready to implement <work-description>
```

## Quick Reference

| Step | Purpose |
|------|---------|
| 1 | Extract work description from user (or ask) |
| 2 | Detect branch naming convention from CLAUDE.md or recent branches |
| 3 | Suggest branch name + confirm with user |
| 4 | Set `.worktree/` as directory |
| 5 | Check gitignore, add to `.git/info/exclude` if needed |
| 6 | Create worktree: `git worktree add .worktree/$BRANCH -b $BRANCH` |
| 7 | Run `pnpm install` / `cargo build` / etc |
| 8 | Run tests to verify baseline |
| 9 | Report ready status |

## Common Mistakes

### Skipping branch name confirmation

- **Problem:** User gets worktree with unexpected branch name
- **Fix:** Always suggest and confirm before creating (Step 3)

### Skipping ignore verification

- **Problem:** Worktree contents get tracked, pollute git status
- **Fix:** Always use `git check-ignore .worktree` before creating (Step 5)

### Using `.gitignore` for local ignores

- **Problem:** Local tooling ignore rules get committed
- **Fix:** Use `.git/info/exclude` for local-only rules (not committed)

### Proceeding with failing tests

- **Problem:** Can't distinguish new bugs from pre-existing issues
- **Fix:** Report failures, get explicit permission to proceed (Step 8)

### Not detecting naming convention

- **Problem:** Suggests branch name that violates project rules
- **Fix:** Always check CLAUDE.md or recent branches first (Step 2)

## Example Workflow

```
User: /using-git-worktrees, let's implement login feature

[Step 1] Work description: "implement login feature"
[Step 2] Detect convention from CLAUDE.md: "feat/"
[Step 3] AskUserQuestion → options: feat/login (Recommended), feat/login/260607 → User picks feat/login
[Step 4] Directory: .worktree/
[Step 5] Check ignore - git check-ignore .worktree → not ignored
         Add to .git/info/exclude
[Step 6] Create: git worktree add .worktree/feat-login -b feat/login
[Step 7] Run: pnpm install
[Step 8] Run: pnpm test → 47 passing

Worktree ready at .worktree/feat-login
Tests passing (47 tests, 0 failures)
Ready to implement login feature
```

## Red Flags

**Never:**
- Skip branch name confirmation (Step 3)
- Create worktree without verifying it's ignored (Step 5)
- Skip baseline test verification (Step 8)
- Proceed with failing tests without asking
- Use `.gitignore` for local tooling rules
- Skip naming convention detection (Step 2)

**Always:**
- Detect work intent first (Step 1)
- Check CLAUDE.md for naming convention (Step 2)
- Confirm branch name with user (Step 3)
- Use `.worktree/` as project-local directory (Step 4)
- Use `.git/info/exclude` for local ignores (Step 5)
- Verify directory is ignored before creating (Step 5)
- Auto-detect and run project setup (Step 7)
- Verify clean test baseline (Step 8)

## Integration

**Called by:**
- **brainstorming** (Phase 4) - REQUIRED when design is approved and implementation follows
- **subagent-driven-development** - REQUIRED before executing any tasks
- **executing-plans** - REQUIRED before executing any tasks
- Any skill needing isolated workspace

**Pairs with:**
- **finishing-a-development-branch** - REQUIRED for cleanup after work complete
