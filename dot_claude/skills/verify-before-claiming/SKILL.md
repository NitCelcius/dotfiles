---
name: verify-before-claiming
description: Tags claims as runtime-verified or inferred. Use before calling a behavior working or broken from code reading alone, or when the user reports otherwise.
---

# Verify Before Claiming

The failure mode: tracing a code path, seeing that it looks wired up correctly, and
reporting "this works" or "this is implemented" — when nobody actually ran it. Code
that reads correctly and behavior that occurs at runtime are two different claims;
only one of them is checkable by reading.

**Announce at start:** "Verifying before I claim this, not just reading the code."

## When this fires
- About to tell the user a feature works, a bug is fixed, or a behavior is
  implemented/broken, and the only evidence so far is source reading.
- The user has already told you the observed behavior (e.g. "it doesn't work in
  practice") — this fires to stop you from re-asserting the code-reading conclusion
  over their report.
- Skip when the claim is genuinely a pure-logic claim with a test as the real
  observation (see CLAUDE.md "Claiming Done"), or the user only asked "where is X
  defined," not "does X work."

<HARD-GATE>
Do not present an INFERRED conclusion as fact. Say it's inferred and name the exact
step that would upgrade it to VERIFIED-RUNTIME.
</HARD-GATE>

## Process
1. If the user already reported the actual behavior, treat that as ground truth.
   Don't re-derive "should work" from the code — go find why the code doesn't match
   reality.
2. Otherwise, before stating a works/broken/implemented claim, ask: is this
   VERIFIED-RUNTIME (you executed it, checked DevTools/console/output) or INFERRED
   (you read the code and it looks right)?
3. If INFERRED and verification is cheap (run the test, curl the endpoint, load the
   page), just run it.
4. If verification is expensive or requires environment you don't have, say so, tag
   the claim INFERRED, and give the user the one command or manual step that would
   confirm it.
5. Never let an agent's report of its own work stand as verification of the running
   system — check it against an artifact the agent didn't author.

## When A Second Agent Is Worth It

A verifier subagent costs a round trip and a second context. Spend it only when
**all three** hold:

1. **The mistake would survive the mechanical checks.** Typecheck, lint and unit
   tests would pass with the error still in place.
2. **A human reading the output would not catch it either.** Numbers, large
   classifications, external state — results with no obviously wrong shape.
3. **Fixing it later costs more than the verifier does.** Work downstream has
   already been built on it, or the operation is not reversible.

Two out of three is a no. So is "this feels important".

This test is for a verifier you dispatch unprompted. When the user asks for a second
opinion — for any reason, a hunch included — arrange it without asking them to
justify it. The artifact rule below still applies.

| Work | Verifier? | How |
|---|---|---|
| Numeric analysis, benchmarks | Yes | Hand it the input fixture and the produced numbers. Ask it to derive the expected values itself |
| Bulk classification of many items | Yes | A random sample of ~20, the rule text, nothing else |
| Plan for a destructive operation | Yes | It reviews the plan artifact (the CSV, the file list), never the prose describing it |
| Quality of a skill's judgment | No — that is a fixture test | A recorded case with an expected answer, re-run on change. Not a per-run agent |
| Root cause investigation | No by default | `measure-first` already covers this. Only when the observation is expensive and one-shot |
| Ordinary small edits, CRUD, trivial refactors | No | The mechanical checks catch these, which is condition 1 failing |

### Give it the artifact, not your reasoning

A verifier handed your summary, your diff rationale, or your transcript will
retrace your reasoning and agree with it. That is not a second opinion; it is the
same opinion at twice the price.

Give it exactly three things: the rule the result has to satisfy, the input, and
the output produced. Not how the output was arrived at, and not what you expect it
to conclude. Say up front which artifact will settle the disagreement if it
returns something different.

## Don't
- Don't blend INFERRED and VERIFIED-RUNTIME claims in the same sentence without
  distinguishing them.
- Don't treat "the tests pass" as proof for integration-shaped claims (wiring,
  event binding, device/scene state) — see CLAUDE.md "Claiming Done".
