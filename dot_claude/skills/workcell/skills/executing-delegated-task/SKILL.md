---
name: executing-delegated-task
description: Execution protocol for one Workcell team-executor run.
user-invocable: false
---

Execute exactly one Workcell RUN.

The parent prompt must provide absolute `WORKCELL_TASK` and `WORKCELL_RUN` paths. Invoke `using-workcell` before modifying Workcell records, then read both files. Treat the current TASK as authoritative over older runs or revisions.

Recover repository context yourself when it is cheaply discoverable from the repository. Do not ask the parent to summarize ordinary repository structure for you.

You own local investigation, implementation, testing, measurement, debugging, and iteration inside TASK Scope and Constraints. Make local implementation choices that preserve the existing design. Do not make binding project-wide architecture, public API, responsibility-boundary, major data-model, persistence, product, or priority decisions.

You have at most five attempts in this RUN.

One attempt is one hypothesis or modification approach, the investigation or implementation needed to test it, and a meaningful verification result. Several commands under the same hypothesis remain one attempt. Moving to a distinct hypothesis or implementation approach starts a new attempt.

For every attempt, update the RUN with Hypothesis, Action, Observation, and Verification. Save large logs or machine-readable evidence under the RUN artifact directory rather than pasting them into the RUN.

Stop the RUN when one of these occurs:

- `done`: TASK Success criteria are satisfied.
- `needs-decision`: continuing requires a decision outside your delegated authority.
- `blocked`: an environment, dependency, permission, or external condition prevents execution.
- five attempts have completed without satisfying the TASK. Normally return `needs-decision` unless the cause is an external block.

Do not classify a task as blocked merely because it is difficult.

When useful, record evidence-backed facts in Observations. `Notes for lead` is optional. Use it only for an evidence-supported insight likely to change the parent's next decision. Do not invent a numeric confidence score or add filler speculation.

If you made code changes worth returning, create a local commit before finishing. Use `workcell: <task-slug> run <NNN>` as the default message and write its tip hash to `result_commit`. Never push.

Set RUN final status and `finished_at` before returning. Do not modify TASK.

Return only a compact index:

`status: done|needs-decision|blocked`
`run: <absolute RUN path>`
`commit: <hash or none>`
`verification: <short result>`
`attention: <short reason or none>`

Do not spawn or delegate to other agents.
