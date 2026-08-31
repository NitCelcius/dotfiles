---
name: readonly
description: Use when the user explicitly scopes a session to investigation, debugging, or codebase archaeology with no edits yet (e.g. "readonly", "planning only", "just look into this, don't touch anything"). Verify assumptions, cite file:line evidence, and end with a decision note that is presented in chat and saved only if asked. Do NOT edit files or run git-write commands until the user asks to implement. Distinct from hear-my-plan, which reorganizes a long new-feature idea dump rather than an investigation task.
---

# Readonly

The user is asking for understanding, not code — but the default failure mode is
answering with a plausible story from a partial read, or drifting into edits once
something interesting turns up. Neither is acceptable here: investigate for real,
and don't touch the tree.

**Announce at start:** "Readonly — no edits until you say go."

## When this fires
- The user states the session is investigation/planning/debugging only, explicitly.
- Skip when the target and change are already both explicit (act directly), or when
  the message is a new-feature/idea dump — that's `hear-my-plan`.

<HARD-GATE>
No Edit/Write/NotebookEdit, and no git command that writes (add, commit, checkout,
reset, rebase), until the user explicitly asks to implement. Reading, running
read-only commands, and dispatching read-only subagents are fine.

The one write this skill ever makes is saving the note to Notion, and only after
an explicit yes to the question in "Output & stopping". Never save unprompted.
</HARD-GATE>

## Process
1. Investigate with real evidence: read the actual source, run read-only commands.
   Do this inline by default — a single sequential read answers most questions.
2. Optionally fan out subagents for independent lanes, but only when the scope is
   genuinely wide, and only after asking the user. Say how many agents and what
   each lane covers, then wait for a go-ahead (see `archaeology-fanout` for the
   sizing check).
3. Verify claims before asserting them — see `verify-before-claiming`. Don't let a
   plausible code-reading story stand in for something you actually ran.
4. Write findings as a note:
   1. The question asked
   2. Findings, each with file:line or command output as evidence
   3. Options considered, with tradeoffs — **only when something was actually being
      decided.** A "how does X work" question has no options; skip the heading
      rather than manufacturing alternatives to fill it.
   4. Recommendation — same condition. Skip it when nothing was proposed.
   5. Open questions — what's still unverified
5. Present the note. Stop.

## Output & stopping
- Present the note in chat as markdown. Do not save it anywhere yet.
- Then ask whether to save it. Saving is opt-in: most investigations don't need to
  outlive the session, and the write costs a schema fetch plus a page create.
- On a yes, save to the **Codebase Investigation Notes** database —
  `collection://38e150ad-0ae3-419a-9f18-f2d90948142a`:
  - `fetch` that data source first. Its response lists the existing `Repo` and
    `Topic` options. Reuse one; mint a new option only when nothing fits. Drift is
    what turns a multi-select into a column you can't filter by.
  - `Question` — the question that opened the session, phrased as a question, not
    as a summary of the answer.
  - `Repo` — basename of `git rev-parse --show-toplevel`.
  - `Commit` — `git rev-parse --short HEAD`. This is what makes the note's decay
    checkable later: `git log <sha>..HEAD -- <the paths the note cites>`.
  - `Created` autofills. Set nothing else.
- After presenting: ask whether to implement now, save the note and stop, or dig
  further. Never auto-chain into edits.

## Don't
- Don't treat "interesting, let me just fix this" as license to edit mid-investigation.
- Don't present an inferred conclusion as verified — tag it (see `verify-before-claiming`).
- Don't auto-invoke `hear-my-plan`'s build-plan structure — a decision note is not
  an execution plan; skip sections that don't apply rather than forcing the shape.
- Don't save the note without being asked, and don't treat "that was useful" as a yes.
