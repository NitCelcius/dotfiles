---
name: writing-plans
description: Writes an implementation plan from a spec. Use for multi-step tasks, before touching code.
---

# Writing Plans

## Overview

Write comprehensive implementation plans that show which files to touch, what changes to make, and how to verify them. DRY. YAGNI. Frequent commits.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Save plans to:** `docs/plans/YYYY-MM-DD-<feature-name>.md` — see "When A Plan
Becomes A Handoff" below for when a plan is worth writing at all, and where one
goes when the work has no repo.

## Scope Check

If the spec covers multiple independent subsystems, suggest breaking it into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each is responsible for. This section goes first in the plan document.

- Design units with clear boundaries. Each file has one clear responsibility.
- Files that change together should live together.
- In existing codebases, follow established patterns.
- Before planning a hand-written loop, parser or I/O routine, check whether the standard library or an existing dependency already does it.

## Code Examples

**Show one representative example per pattern — not one per file.**

If tasks 2, 3, and 4 all follow the same structural change (e.g., "rename class X to Y in each file"), show the full example once in task 2, then reference the pattern in tasks 3 and 4:

```markdown
- [ ] **Step: Apply same rename as Task 2 to `styles/stage-1-3.css`**
  (Pattern: same as Task 2 — replace `.s12-note` with `.u-note`)
```

Do NOT repeat the full code block for every file when the pattern is identical. The goal is a readable plan, not a transcript.

## Unexpected Patterns

**If implementation reveals a case that doesn't fit the plan's pattern:**

Stop before committing. Report to the user:
- What the plan assumed
- What you actually found
- The options you see

Do not commit a workaround silently. Get explicit guidance first.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Apply the rename to `file.css`" — step
- "Verify no references remain" — step
- "Commit" — step

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

**Goal:** [One sentence describing what this builds]

**Status:** [Where the work stands right now: last completed task, what is next,
and what is blocked on whom]

**Last verified:** [Date, the exact command run, and its result. "Not yet" is a
valid answer and a useful one]

**Resume:** [The directory to start from and the command that gets a cold session
back to work, e.g. `cd analysis && uv run python run.py`]

**Architecture:** [2-3 sentences about approach]

**Affected files:**
- `exact/path/to/file.ext` — what changes
- `exact/path/to/other.ext` — what changes

**Invariants:** [Existing abstractions, public interfaces, or output compatibility
that must NOT change while executing this plan]

**Deferred gates:** [Verification steps that could not be run yet, and why]

---
```

The header is the part that gets re-read. Keep it short enough to be useful as a
range read, and update **Status**, **Last verified** and **Deferred gates** as
tasks complete. A later session reads this block first and only then pulls in the
tasks it needs.

Only routing belongs up here: where the work stands, whether **Status** can be
trusted, how to start again, and which gates have not run. **Last verified** is
what stops **Status** from being a claim — "Task 4 done" and "the suite passed on
2026-09-11 with `uv run pytest -q`" are different assertions, and a cold session
cannot tell them apart from **Status** alone.

## Unverified Claims Go Inline, Not In The Header

An assumption belongs next to the thing it qualifies, not collected at the top.
Gathered into the header they grow past a useful range read, and they end up far
from the task a later session is actually reading — which is exactly how an
assumption gets treated as a fact.

Tag them where they sit, using the same vocabulary as `verify-before-claiming`:

```markdown
- [ ] **Step 2: Point the loader at `data/out/merged.csv`**

  INFERRED: the column order matches `selections_all.csv`. Read the header row
  before relying on it; if it differs, Task 5's export needs the same fix.
```

- `VERIFIED-RUNTIME` — executed and observed
- `VERIFIED-CODE` — read the path end to end
- `INFERRED` — reading suggests it, nobody ran it

An untagged statement in a plan reads as fact. If you are not willing to tag it
`VERIFIED-*`, tag it `INFERRED` rather than leaving it bare.

## When A Plan Becomes A Handoff

Multi-session work needs the header from the start, not written in a hurry at the
end — by then the session that knew what was uncertain is the one being replaced.

Start the header as soon as **two** of these hold, and fill in the tasks after:

1. The work will not finish in one session, or a compaction has already happened
2. It spans three or more files, or changes state outside the repo (files moved,
   a service deployed, a database written)
3. Backing it out would be expensive: destructive steps, or numbers that flow
   downstream into other work
4. Two or more assumptions are still unconfirmed

One or none of these, and a plan document is overhead. Do not write one.

**Where it lives:** work inside a repo goes to `docs/plans/YYYY-MM-DD-<name>.md`,
where it is versioned and reviewable alongside the change. Work with no repo —
file reorganisation, cross-tool investigations — goes to `~/.claude/plans/`.

## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Modify: `exact/path/to/existing.ext`

- [ ] **Step 1: [Action]**

```language
// Show the change, with before/after or just the new code if it's a creation
```

- [ ] **Step 2: Verify**

Run: `command to verify`
Expected: what you should see

- [ ] **Step 3: Commit**

```bash
git add exact/path/to/file.ext
git commit -m "refactor: description"
```
````

## No Placeholders

These are **plan failures** — never write them:
- "TBD", "TODO", "implement later"
- "Add appropriate error handling"
- "Similar to Task N" (when the code is actually different — repeat the code)
- Steps that describe what to do without showing how

It IS acceptable to write "Pattern: same as Task N — apply X" when the code is genuinely identical.

## Language

When writing the plan in Japanese, do not use dash characters (—, –, ―) and do not
insert English words that are not strictly necessary. This applies to the
generated document, not to this skill file.

## Remember
- Exact file paths always
- Exact commands with expected output
- DRY, YAGNI, frequent commits
- One representative code example per pattern

## Self-Review

After writing the complete plan, check it against the spec:

1. **Spec coverage:** Can you point to a task that implements each requirement? List any gaps.
2. **Placeholder scan:** Search for red flags from the "No Placeholders" section. Fix them.
3. **Consistency:** Do method/class/file names in later tasks match what was defined earlier?

Fix issues inline. No need to re-review — just fix and move on.
