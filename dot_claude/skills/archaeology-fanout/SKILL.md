---
name: archaeology-fanout
description: Traces how a feature works across large or unfamiliar code. Use for "how does X work" questions too big for one sequential read.
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
   cover. Run lanes on the Haiku agents wherever they can do the job:
   `haiku-observer` for the git-history lane, `haiku-finder` and `haiku-reader` for
   code and doc lanes. They start without CLAUDE.md, so each task names the exact
   commands or paths, and asks for the answer plus the lines it rests on rather than
   raw output. Judging and reconciling stay in main. When every lane runs on a Haiku
   agent, launch without a go-ahead; otherwise get one first. Then launch them as
   parallel Agent calls in one message. Each must return file:line evidence, not summaries
   without citations. Do not let lanes see each other's conclusions before they
   finish — that's what prevents one lane's guess from contaminating another's
   independent read.
4. Reconcile in a synthesis pass. Check each SHA or file:line a conclusion rests on
   yourself before building on it. Tag every claim:
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
  — lead with concept (step 6). The tiers apply to an inline answer too, not only
  to a fanout.
