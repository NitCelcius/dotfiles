---
name: unattended-run
description: Use only when the user explicitly invokes /unattended-run to start work nobody is watching. Turns permission prompts from the git gate and permissions.ask into denials with a reason, and sets what the run may do alone and what it reports.
disable-model-invocation: true
hooks:
  PreToolUse:
    - matcher: "Bash|PowerShell"
      hooks:
        - type: command
          command: python ~/.claude/git-gate/git_gate.py --unattended
          timeout: 30
---

# Unattended run

Nobody is watching this session. A permission prompt would stall it until someone comes
back, so from now until the session ends, the git-gate hook denies, with a reason, every
command that would otherwise ask:

- anything a `permissions.ask` rule matches: PR create/merge/close, issue close,
  `reset --hard`, force-with-lease pushes, remote branch deletes
- `git branch -D` of a branch that is on a remote but has commits on no remote
- a push with a `+refspec` (force) or a `:refspec` (remote delete)

## Rules

- Do not wait on the user. Where you would normally ask, take the reversible option that
  keeps the most choices open, note the assumption, and continue. If nothing reversible
  exists, skip that part.
- A command denied for this run is not retried, split, or rephrased to get past the
  check (through `git -C`, another shell, a script file). Skip it and carry on with the
  work that does not depend on it.
- Cleared without asking: WIP commits, a non-force push of the working branch, rebase,
  removing worktrees this run created, and `git branch -D` of a branch that is local-only
  or fully pushed.
- Never open a PR: the user reviews it before anything is published. When the work is
  ready for one, run `draft-pr` steps 1–3 and stop there: carry step 2's findings into
  the final report instead of waiting on them, and leave the body in its file and the
  title for the final report.
- Before a forced branch delete, record the tip's full SHA (`git rev-parse <branch>`).
  The delete also removes the branch's reflog, and once its worktree is gone nothing else
  points at an unpushed tip; gc prunes it after about two weeks.

## Final report

Close out with the usual headings, plus these when they have entries:

- `# PR draft` — the body file's absolute path, the proposed title on one line, and the
  findings from the `draft-pr` checks.
- `# Skipped (needs approval)` — each denied command verbatim, the hook's reason, and
  what it would have done.
- `# Deleted branches` — `<repo> <branch> <full SHA>` per forced delete, restorable with
  `git branch <branch> <SHA>`.
