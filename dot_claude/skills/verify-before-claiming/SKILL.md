---
name: verify-before-claiming
description: Use before asserting that a behavior works, is implemented, or is broken, when the evidence so far comes only from reading code rather than running it. Tag each such claim as VERIFIED-RUNTIME or INFERRED and say what would upgrade it. Also applies when the user already reports the opposite of what the code suggests — trust their observation over the code reading.
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

## Don't
- Don't blend INFERRED and VERIFIED-RUNTIME claims in the same sentence without
  distinguishing them.
- Don't treat "the tests pass" as proof for integration-shaped claims (wiring,
  event binding, device/scene state) — see CLAUDE.md "Claiming Done".
