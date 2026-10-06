---
name: unattended-run
description: Runs work nobody is watching without stalling on prompts. Use only when the user explicitly invokes /unattended-run.
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
- `git branch -D` of a branch that is on a remote but has commits on no remote, or in a
  repo the hook cannot pin down (`GIT_DIR`, `--git-dir`, `env -C`, a `cd` in a subshell)
- a force push (`+refspec`, `--force`) or a push that deletes remote branches
  (`:refspec`, `--delete`, `--mirror`, `--prune`)

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
- Move or drop branches only with `git branch -D`. The hook does not check the other ways
  to overwrite one (`update-ref`, `branch -f`/`-M`/`-C`, `checkout -B`, `switch -C`,
  `fetch . +a:b`), so whether those prompt depends on the permission mode.
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
