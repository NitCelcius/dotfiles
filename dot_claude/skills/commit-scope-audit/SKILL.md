---
name: commit-scope-audit
description: Use before staging or committing, or before splitting work into multiple commits. Audits git status and already-staged changes first, proposes a commit plan naming exact files, and waits for approval before running git add or git commit. Prevents pre-staged or unrelated files from riding along in a commit.
---

# Commit Scope Audit

The failure mode: `git add` sweeps in a file that was already staged before this
session started (a pre-staged rename, a WIP experiment), and it rides into a commit
the user didn't intend to include. Unwinding that costs an amend/reset cycle.

**Announce at start:** "Auditing staged changes before I commit anything."

## When this fires
- About to run `git add` or `git commit` for the first time in a session.
- About to split working-tree changes into more than one commit.
- Skip when the user has already approved an exact file list for this exact commit
  in this same turn.

<HARD-GATE>
Do not run `git add` on anything not explicitly named or clearly in-scope. Do not
run `git commit` until the file list for that commit has been stated and, for a
multi-commit split, approved.
</HARD-GATE>

## Process
1. Run `git status --porcelain` and `git diff --cached --stat` first. Report three
   buckets explicitly: (a) unstaged changes, (b) already-staged changes, (c)
   untracked files. Flag anything staged that predates this session's work.
2. Confirm with the user which of these are in scope. Anything not named is out of
   scope by default.
3. For a single commit: state the exact file list before staging.
4. For a multi-commit split: propose N commits as file-list + message each, grouped
   by logical concern (behavior vs. test vs. config vs. rename) not file type. Wait
   for approval before running any `git add`/`git commit`.
5. After each commit, run `git show --stat` and confirm the file list matches the
   plan. If it doesn't, stop and report — don't amend silently to fix it.
6. Apply the repo's signing fallback rule as-is (see CLAUDE.md "SSH signing
   fallback") — this skill governs scope, not signing.

## Don't
- Don't use `git add -A` or `git add .` — name files.
- Don't fold an unrelated pre-staged file into "might as well commit it together."
- Don't re-litigate an already-approved file list mid-commit; if new files appear,
  treat that as a new decision point, not silent scope creep.
