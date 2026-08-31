---
name: archaeology-fanout
description: Use for "how does X work" or trace-this-feature investigations in unfamiliar or large code. Sizes the question first, then — only when the material justifies it and the user agrees — fans out parallel subagents across independent lanes (spec/docs, backend, frontend, git history, tests, feature-flag gating) instead of answering from a single sequential read, and reconciles with confidence tags. Pairs with verify-before-claiming for the reconciliation step.
---

# Archaeology Fanout

A single sequential read of a large feature tends to answer from whichever file
was opened first, and misses contradictions between what the spec says and what
the code actually does. Fanning out independent lanes in parallel, then
reconciling, catches those contradictions instead of averaging over them.

A fanout is the expensive path, and most repos are not large enough to need it.
The sizing step below is not a formality — skipping it turns a two-file question
into six agents.

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
2. Size it before spawning anything. Check the repo has the material the lanes
   assume — `git rev-list --count HEAD` for a history lane, the file count in each
   lane's area for the rest. Two or fewer surviving lanes, or a history too short
   to hold a rationale, means this is a sequential read: do it inline and go to
   step 4.
3. If a fanout still earns its cost, state the lane count and what each lane will
   cover, and get a go-ahead before launching. Then launch them as parallel Agent
   calls in one message. Each must return file:line evidence, not summaries
   without citations. Do not let lanes see each other's conclusions before they
   finish — that's what prevents one lane's guess from contaminating another's
   independent read.
4. Reconcile in a synthesis pass. Tag every claim:
   - `VERIFIED-CODE` — read the path end to end
   - `VERIFIED-RUNTIME` — actually executed/observed it
   - `INFERRED` — code reading suggests this, not run (see `verify-before-claiming`)
   - `CONTRADICTION` — lanes disagreed; give both views
5. For any claim tagged INFERRED where the question was "does this work," name the
   one command or step that would upgrade it.
6. Answer in tiers, stopping for go-ahead after each unless the user asked for full
   depth upfront:
   1. Concept (~5 sentences, sourced from spec/docs, not from UI resource strings)
   2. Module/layer boundaries
   3. Concrete call chain with file:line

## Don't
- Don't launch a fanout without the sizing check — a small repo answers faster
  sequentially than it does through six agent round-trips.
- Don't skip the reconciliation step and just concatenate lane outputs.
- Don't derive a feature's official name or intended behavior from UI strings when
  a spec/design doc lane is available.
- Don't open with the file:line call chain when the user asked "what does this do"
  — lead with concept, per CLAUDE.md.
