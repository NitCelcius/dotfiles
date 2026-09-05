---
name: workcell-delegate
description: Execute the currently approved plan with Workcell delegation enabled. Use only when the user explicitly invokes /workcell-delegate.
disable-model-invocation: true
---

Execute the currently approved plan with Workcell delegation enabled.

This skill does not create a plan. If the current context does not contain a sufficiently concrete approved plan, do not start implementation. Tell the user the plan is not ready for Workcell execution.

The Workcell authorization applies only to the plan active when this skill was invoked. Do not carry it into a later or substantially different plan.

Main remains responsible for the whole plan. Direct execution by main is the default. Delegate only when doing so meaningfully isolates exploration or iteration, gives a bounded independently verifiable task, or otherwise reduces main-context cost without forcing main to relearn the entire result.

For each delegated executor task:

1. Decide a bounded Goal, Scope, Constraints, and observable Success criteria.
2. Invoke `using-workcell`, then create the task with `workcell task create <slug>`.
3. Fill `TASK.md` as main. Do not make the executor rediscover facts that only exist in the user conversation. Do not summarize repository facts that the executor can cheaply recover itself.
4. Set TASK status to `ready` when its contract is complete.
5. Create a RUN with `workcell run create <task-dir>` and set TASK status to `running`.
6. Spawn a fresh `team-executor` with these absolute paths in its prompt:

   `WORKCELL_TASK: <absolute TASK.md>`
   `WORKCELL_RUN: <absolute run-NNN.md>`

   Do not duplicate the TASK body into the Agent prompt.
7. Never resume a completed executor instance. If the same Goal continues after a decision or failure, revise TASK and create a fresh RUN and fresh executor.
8. Keep at most three `team-executor` instances active at once. Parallelize only truly independent tasks. Never run two active RUNs for the same TASK.

Review executor results progressively: return index first, then commit diff, then RUN, then artifacts only as needed.

For `done` with passing verification, review the commit diff. If acceptable, cherry-pick it into main and rerun relevant verification in main. Mark TASK `done` only after main-side verification succeeds.

Do not automatically integrate `needs-decision` or `blocked` changes.

Use `team-advisor` only when both are true:

- technical uncertainty is substantial enough that main cannot decide confidently from existing evidence; and
- a wrong decision has material risk or rework.

Typical cases include architecture or responsibility placement, concurrency, authentication/authorization, migration, destructive compatibility changes, and structural implementation problems that local fixes do not resolve. Five failed executor attempts alone are not a reason to call the advisor.

Ask the human only for choices that repository evidence and technical analysis cannot decide, such as intended behavior, priorities, compatibility preference, UX preference, acceptable risk, or operational policy. Main is the only human-facing question channel. Use `using-workcell` for the question format. Present questions as they arise rather than saving them until the end. Combine questions that depend on the same human decision.

If an executor needs uncommitted main state, create a `WIP: ...` checkpoint commit before spawning it. Whether that checkpoint reaches the executor depends on `worktree.baseRef`: with `head` the worktree branches from local HEAD and the checkpoint is sufficient, while under the default `fresh` it branches from `origin/<default-branch>` and local commits are not visible at all. Set `worktree.baseRef` to `head` when delegating on top of branch work. Do not push WIP commits from a branch not beginning with `wip/` unless the human first decides to create a WIP branch and names it.

At plan completion, main owns WIP-history cleanup. Rebase or squash as appropriate so the human can inspect the process and resulting history before moving from `wip/*` to a normal branch.

When the current plan completes, is abandoned, or changes Goal substantially, Workcell authorization ends.
