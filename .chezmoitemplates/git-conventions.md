{{- /* Git conventions shared by Claude Code and Codex. Included by          */ -}}
{{- /* dot_claude/skills/git-workflow/SKILL.md.tmpl and dot_codex/AGENTS.md.tmpl. */ -}}
## Ignore patterns
Use `.git/info/exclude` for local-only ignore patterns (e.g. worktree directories).
Do not add personal/local entries to `.gitignore`.

## Branch naming
- Bug fixes: `bugfix/(name-of-thing)` — preferred; `fix/` is acceptable
- Features: `feat/(name-of-something)`
- Append date as `YYMMDD` suffix only to avoid name conflicts, e.g. `feat/(name)/260328`
- WIP branches: prefix with `wip/`, e.g. `wip/bugfix/(name)`, `wip/feat/(name)`

## Commit messages
- Follow conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `chore:`, `style:`, `docs:`
- WIP commits: `WIP: <type>(<feature, optional>): <change>`, e.g.
  `WIP: feat(auth): refresh expired tokens`. A commit that is not WIP drops the
  `WIP:` prefix.
- Subject: what was done. Body: usually about two lines on how it was done — the code
  should explain the rest. Write for someone who never saw the session: no task
  numbers or other session-internal references. Include the issue number when working
  on an issue.
- Omit the body when the diff is self-evident: a config-only change, or about 10 lines
  or fewer.
- A message written to a file for `git commit -F` goes in the repo's git dir as a `.md`
  file (`git rev-parse --absolute-git-dir`, which also resolves in a worktree), nowhere
  else.

## Pushing
Always name the remote and branch: `git push -u origin <branch>`. Never a bare
`git push` or `git push origin HEAD` — a branch created from `origin/main` tracks main,
so a bare push lands there. Push to the default branch only when I approved it for that
repo (e.g. a PoC).

## Rewriting others' state
Never force-push without first showing `git log --oneline @{u}..` (what you'd overwrite)
and waiting for confirmation. Never `git checkout <other-branch> -- <paths>` into the
current working tree — create a worktree instead ([[using-git-worktrees]]).

## Fetch before diverging
Always `git fetch origin` immediately before `rebase`, `merge`, or reasoning about
whether a branch has diverged — never rebase onto or reason about a stale local ref.

## Rebasing
Before `git rebase --onto <target>`, always `git fetch` first and rebase onto the
fetched `origin/<target>` ref, not a possibly-stale local branch ref — unless the goal
is specifically to preserve local history as-is (e.g. deliberately rebasing onto a
known-stale local snapshot). Fetching is cheap; a stale local ref can silently diverge
from `origin/<target>` when someone else rebased or force-pushed it, producing a
result that looks correct locally but conflicts against the real upstream.

## Merge strategy
Rebase and merge (GitHub's rebase-merge). Not squash merge.
GitHub recreates every commit when it rebase-merges, so no signature reaches `main`,
whether the branch commit was signed or not. A signature only needs to be on the
branch the PR merges from.

## Reporting whether a branch is merged
GitHub's rebase & merge rewrites commits, so `git branch --merged` can call a merged
branch unmerged. Check in this order:
1. `git fetch origin`
2. `gh pr list --state merged --head <branch>` (bare branch name, no `origin/`). A hit
   means a PR from that branch merged, not that every commit on the branch did.
3. `git cherry -v origin/main <branch>`. Lines starting with `-` are already on main by
   content; any line starting with `+` is not, so the branch is not fully merged. A
   commit edited while rebasing (e.g. conflict resolution) shows `+` although its PR
   merged: look for its subject with `git log origin/main --grep`.

`git branch -r --merged origin/main` proves merged only; its absence proves nothing.

## SSH signing fallback
If the signing agent is unavailable mid-commit, retry with `--no-gpg-sign` immediately.
Do not ask, do not investigate the cause — an unsigned WIP commit is never worth
interrupting the work for.
When the task is done, state plainly that the commits were made without signing.
Since only the branch needs signatures (see Merge strategy), signing is reconciled
once, at PR time, not during the work — see the `draft-pr` skill.
