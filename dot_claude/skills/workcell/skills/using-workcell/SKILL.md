---
name: using-workcell
description: Workcell storage, TASK, RUN, question, artifact, revision, and CLI protocol.
user-invocable: false
---

Use this skill only for Workcell record structure and file protocol. It does not decide whether work should be delegated or how code should be implemented.

Workcell root is `~/.local/share/workcell` unless `WORKCELL_ROOT` overrides it. Records are outside Git worktrees and are analysis records, not cross-device execution state.

The canonical Markdown templates are in this skill's `templates/` directory. Follow them rather than recreating formats from memory.

## CLI

The session start hook reports the CLI's absolute path and the record root. Invoke it as `python "<reported path>"`, or as `workcell` when a shim is on PATH.

`workcell task create <slug>` creates one task directory and prints its absolute path.

`workcell task revise <task-dir>` archives the current TASK as `history/task-rev-NNN.md`, increments revision, resets status to `preparing`, and preserves the body for main to edit.

`workcell run create <task-dir>` creates the next `runs/run-NNN.md` and matching `artifacts/run-NNN/`, then prints the RUN absolute path.

The CLI does not create questions, choose statuses, integrate commits, push, rebase, squash, or analyze telemetry.

## TASK ownership

Main owns TASK. Executor reads it but does not edit it. The current TASK is authoritative. Goal changes substantially create a new task; Scope, Constraints, Success criteria, or Parent context changes with the same Goal use revision.

## RUN ownership

One fresh executor owns one RUN. The executor updates it during its work. After that executor finishes, the RUN is immutable. A later executor gets a new RUN.

## Artifacts

Large logs, measurements, JSON, images, and other detailed evidence belong under `artifacts/run-NNN/`. Refer to them from RUN by relative path. Do not store hidden chain-of-thought.

## Questions

Questions are one Markdown file, so main creates them directly from `templates/QUESTION.md` rather than through the CLI. Number them with the next unused `q-NNN-<slug>.md` in the task's date directory `questions/`.

Use `blocking` only when the related work cannot continue without human-only input. Use `advisory` when main can state a provisional action and continue. Human answers arrive through normal chat; main records the answer and marks the file answered.
