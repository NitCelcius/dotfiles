# hear-my-plan

You are running the `hear-my-plan` skill. The user has shared a plan and wants validation before implementation. Follow these steps in order. Do not write any code or make any edits until Step 5 is confirmed.

## Step 1: Git Safety Check

Run `git status` and `git branch --show-current` in parallel.

**Branch check** — if the current branch is `main`, `master`, or `production`, AND the user's plan involves editing files (not just asking a question), use AskUserQuestion:
> "You're on `<branch>`. Do you want to create a branch `feat/<inferred-name-from-plan>` first, or proceed on `<branch>` anyway?"

**Pending changes** — report any uncommitted tracked files or untracked files, excluding extensions: `.md`, `.pdf`, `.txt`, `.docx`, `.png`, `.jpg`. Scale the message to the count:
- 1–2 files: "Note: you have some pending changes — [list them]."
- 3+ files: "You have several pending changes ([list]). Do you want to commit them to `<current-branch>` before we start?"

If the user says to proceed anyway, continue to Step 2.

## Step 2: Read Context

Read the project `CLAUDE.md` and `.claude/REF.md` if it exists. Note any conventions or active plans relevant to what the user described.

## Step 3: Discuss

Have a conversational discussion — no bullet-point formality required. Cover:
- Design concerns: maintainability, readability, naming consistency with existing code
- Conflicts with CLAUDE.md conventions or any active plan in REF.md
- Flag if the scope looks like more than one PR (typically 500+ line changes across many files)

Confirm the user agrees with your concerns or explanations before moving on.

## Step 4: Code Preview (skip entirely if the plan only creates new files)

Pick the **first existing file you would edit** — do not open any additional files. Read it, find the most relevant section, and show a short before/after preview (5–15 lines):

```
`path/to/file.ext:LINE` would look like:
[after snippet]
```

Keep it tight — one representative snippet is enough to give a feel for the change.

## Step 5: Confirmation Gate

Use AskUserQuestion: "Ready to proceed?"

Do not take any action until the user confirms.
