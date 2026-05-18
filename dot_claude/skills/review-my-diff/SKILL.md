---
name: review-my-diff
description: Use when asked to review changes on the current branch or uncommitted edits. Accepts an optional base branch argument.
---

# review-my-diff

Review branch or working tree changes against the base, then output a numbered
report.

## Usage

`/review-my-diff [base]` — defaults to `main` when base is omitted

## Steps

1. Determine the scope:
   - If there are uncommitted changes: include both `git diff` (unstaged) and `git diff --cached` (staged)
   - If a base is provided: `git diff <base>...HEAD`
   - If base is omitted: `git diff main...HEAD`
2. Read changed files as needed to understand the context.
3. Output the report in this format:
   - **Issues**: Bugs, regressions, or convention violations with `file:line`
   - **Concerns**: Potential issues, minor items, or points requiring confirmation
   - **Good points**: Noteworthy improvements, if any
4. Do not make any changes. Report only.
