---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

# Writing Plans

## Overview

Write comprehensive implementation plans that show which files to touch, what changes to make, and how to verify them. DRY. YAGNI. Frequent commits.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Save plans to:** `docs/plans/YYYY-MM-DD-<feature-name>.md`

## Scope Check

If the spec covers multiple independent subsystems, suggest breaking it into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each is responsible for. This section goes first in the plan document.

- Design units with clear boundaries. Each file has one clear responsibility.
- Files that change together should live together.
- In existing codebases, follow established patterns.

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

**Architecture:** [2-3 sentences about approach]

**Affected files:**
- `exact/path/to/file.ext` — what changes
- `exact/path/to/other.ext` — what changes

---
```

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
