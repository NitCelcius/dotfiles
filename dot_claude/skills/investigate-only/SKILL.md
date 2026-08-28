---
name: investigate-only
description: Use when the user explicitly scopes a session to investigation, debugging, or codebase archaeology with no edits yet (e.g. "planning only", "just look into this, don't touch anything"). Verify assumptions, cite file:line evidence, and produce a decision note. Do NOT edit files or run git-write commands until the user asks to implement. Distinct from hear-my-plan, which reorganizes a long new-feature idea dump rather than an investigation task.
---

# Investigate Only

The user is asking for understanding, not code — but the default failure mode is
answering with a plausible story from a partial read, or drifting into edits once
something interesting turns up. Neither is acceptable here: investigate for real,
and don't touch the tree.

**Announce at start:** "Investigate-only — no edits until you say go."

## When this fires
- The user states the session is investigation/planning/debugging only, explicitly.
- Skip when the target and change are already both explicit (act directly), or when
  the message is a new-feature/idea dump — that's `hear-my-plan`.

<HARD-GATE>
No Edit/Write/NotebookEdit, and no git command that writes (add, commit, checkout,
reset, rebase), until the user explicitly asks to implement. Reading, running
read-only commands, and dispatching read-only subagents are fine.
</HARD-GATE>

## Process
1. Investigate with real evidence: read the actual source, run read-only commands,
   fan out subagents for independent lanes when the scope is wide (see
   `archaeology-fanout`).
2. Verify claims before asserting them — see `verify-before-claiming`. Don't let a
   plausible code-reading story stand in for something you actually ran.
3. Write findings as a decision note:
   1. Problem statement / question asked
   2. Findings, each with file:line or command output as evidence
   3. Options considered, if any, with tradeoffs
   4. Recommendation
   5. Open questions — what's still unverified
4. Present the note. Stop.

## Output & stopping
- Output as markdown suitable for pasting into Obsidian (or hand to
  `record-to-obsidian` if the user has that skill loaded).
- After presenting: ask whether to implement now, save the note and stop, or dig
  further. Never auto-chain into edits.

## Don't
- Don't treat "interesting, let me just fix this" as license to edit mid-investigation.
- Don't present an inferred conclusion as verified — tag it (see `verify-before-claiming`).
- Don't auto-invoke `hear-my-plan`'s build-plan structure — a decision note is not
  an execution plan; skip sections that don't apply rather than forcing the shape.
