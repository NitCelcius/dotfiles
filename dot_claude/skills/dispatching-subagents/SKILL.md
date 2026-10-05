---
name: dispatching-subagents
description: Decides whether and how to hand work to a subagent. Use before any Agent or Workflow dispatch.
---

# Dispatching subagents

- Dispatch a subagent when the work produces large output that main will not
  need to re-read (verification loops, log triage, cross-repo search).
- Keep it in the main session when the output will be referenced repeatedly.
- Default: return conclusions with file:line references, not raw content.
  Quote source only when the conclusion cannot stand without it.
- Read-only work (search, log triage, inventory) needs no confirmation.
- Before dispatching subagents that write code or edit files, main asks the user
  once, covering the whole batch. Within that batch a subagent executes without
  stopping to ask for routine permission.
- If a subagent hits a decision the batch approval did not cover, it surfaces it
  immediately — it does not guess and keep going, and it does not hold the
  question for its final report. A decision held is more expensive than a
  subagent that stops early, because work built on the wrong branch of it is
  thrown away.
- Delegate work whose result is cheap to verify. If checking the output costs about
  as much as producing it, do it in main instead. Claims a subagent cannot observe
  about itself — whether it was blocked, whether it waited — are never verifiable;
  do not build on them.
- Name the check before dispatching, not after: which artifact will show whether this
  worked, and what failure would look like in it. A check chosen after reading the
  report tends to be one the report already passes. On return, run it against that
  artifact, not against the agent's summary; if a load-bearing claim has no checkable
  artifact, say so rather than passing it through.
- For dispatching an agent purely to *check* a result, see `verify-before-claiming`.
