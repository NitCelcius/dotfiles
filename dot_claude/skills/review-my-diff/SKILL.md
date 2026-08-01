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
3. If the review target is a PR (not just a local/uncommitted diff), also check whether every
   commit in it is signed:
   `gh api repos/{owner}/{repo}/pulls/<n>/commits --jq '.[] | {sha: .sha[0:7], verified: .commit.verification.verified, reason: .commit.verification.reason}'`
   - Signing here is via the **Bitwarden SSH agent** (not the Windows `ssh-agent` service, which is
     disabled on purpose so Bitwarden can own the `openssh-ssh-agent` named pipe). If a local
     `git log --show-signature` reports "No signature" or an `allowedSignersFile` error, that's a
     local-verification gap, not proof the commit is actually unsigned — trust the GitHub API
     result (`verified`/`reason`) over local `git log --show-signature` output.
   - Report any unsigned commits as a Concern in the numbered list below, don't silently pass over them.
4. Output the report in this format:
   - **Issues**: Bugs, regressions, or convention violations with `file:line`
   - **Concerns**: Potential issues, minor items, or points requiring confirmation
   - **Good points**: Noteworthy improvements, if any

   Number every item with a single sequence running across all three categories.
   Do not restart numbering per category — the user replies with bare numbers, so
   each number must point at exactly one item.
4. Do not make any changes. Report only.
