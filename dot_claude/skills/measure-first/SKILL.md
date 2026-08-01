---
name: measure-first
description: Use when a fix did not work and you are about to try another fix. The edit target is known but the cause is not. Design the cheapest observation that separates the candidate causes, run it, report what you observed, then make one fix aimed at that single point.
---

# Measure First

The failure mode this skill exists for: the first fix did not work, so a second
fix goes in on top of a guess, then a third. Each attempt adds code, adds
context, and destroys the evidence that would have identified the cause.

**Announce at start:** "I'm using measure-first before trying another fix."

## When this fires

- A fix was applied, the symptom did not change, and another fix is about to go in.
- The same symptom has been attacked from two different angles already.
- Skip when the first attempt worked, or when the cause is stated outright in an
  error message you have already read.

An explicit edit target does not disable this skill. Knowing which file to edit
is not the same as knowing why it is broken, so the usual "target is explicit,
act directly" shortcut does not apply here.

<HARD-GATE>
Do not apply another fix until you have run an observation and reported what it
showed.
</HARD-GATE>

## Process

1. **State two or three candidate causes.** Not everything possible. Candidates
   that predict different observations. If two candidates predict the same
   observation, they are one candidate for now.

2. **Design the cheapest observation that separates them.** Cheapest means fewest
   tokens and least state change: a printed value, a length, a boolean, one log
   line. Do not take a screenshot when a count would do.

3. **Run it.** Do not bundle a fix into the same step. If the observation needs
   code, that code must be removable in one edit.

4. **Report what you observed**, separated from what you infer from it. Say which
   candidate the observation ruled out.

5. **Make one fix, aimed at the surviving cause.** One. If the observation ruled
   out every candidate, return to step 1 with what you now know and fix nothing.

6. **Remove the observation code** unless it earned a permanent place.

## Notes

- "Add a log and see" counts as an observation only if you say beforehand what
  each possible output would mean. Otherwise it is a guess with extra steps.
- An observation that cannot come out negative is not an observation.
- If the cheapest separating observation is still expensive, say so and ask
  before spending it.
