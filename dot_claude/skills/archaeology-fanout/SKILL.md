---
name: archaeology-fanout
description: Use for "how does X work" or trace-this-feature investigations in unfamiliar or large code. Fans out parallel subagents across independent lanes (spec/docs, backend, frontend, git history, tests, feature-flag gating) instead of answering from a single sequential read, then reconciles with confidence tags. Pairs with verify-before-claiming for the reconciliation step.
---

# Archaeology Fanout

A single sequential read of a large feature tends to answer from whichever file
was opened first, and misses contradictions between what the spec says and what
the code actually does. Fanning out independent lanes in parallel, then
reconciling, catches those contradictions instead of averaging over them.

## When this fires
- An open-ended "how does X work" / "trace this feature" / "why does Y happen"
  question spans multiple layers or an unfamiliar area of a large codebase.
- Skip for a single targeted lookup ("where is X defined") — use a single Explore
  agent instead of a fanout.

## Process
1. Name the lanes that actually apply to this question — typically a subset of:
   spec/design docs, backend/service layer, frontend/UI layer, git history (when
   was this added, stated rationale), test coverage, feature-flag/config gating.
   Skip lanes that don't exist for this codebase rather than forcing all six.
2. Launch the lanes as parallel Agent calls in one message. Each must return
   file:line evidence, not summaries without citations. Do not let lanes see each
   other's conclusions before they finish — that's what prevents one lane's guess
   from contaminating another's independent read.
3. Reconcile in a synthesis pass. Tag every claim:
   - `VERIFIED-CODE` — read the path end to end
   - `VERIFIED-RUNTIME` — actually executed/observed it
   - `INFERRED` — code reading suggests this, not run (see `verify-before-claiming`)
   - `CONTRADICTION` — lanes disagreed; give both views
4. For any claim tagged INFERRED where the question was "does this work," name the
   one command or step that would upgrade it.
5. Answer in tiers, stopping for go-ahead after each unless the user asked for full
   depth upfront:
   1. Concept (~5 sentences, sourced from spec/docs, not from UI resource strings)
   2. Module/layer boundaries
   3. Concrete call chain with file:line

## Don't
- Don't skip the reconciliation step and just concatenate lane outputs.
- Don't derive a feature's official name or intended behavior from UI strings when
  a spec/design doc lane is available.
- Don't open with the file:line call chain when the user asked "what does this do"
  — lead with concept, per CLAUDE.md.
