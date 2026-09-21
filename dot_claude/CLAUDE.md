## Tooling

- Run Python via `uv run python`, not `python3` directly
- Install Python packages via `uv add <pkg>` (CLI), not by editing `pyproject.toml` directly — exception: when a specific version constraint is needed, edit the file
- Use `git mv` for all file/directory moves to preserve history

## Environment

- OS: Windows 11
- Shell: bash and PowerShell are both available. Default to bash; use PowerShell for
  filesystem operations and for parsing external command output — bash mangles
  Windows paths and misreads Shift-JIS.
- PowerShell profile location: resolve with `echo $PROFILE`
- Git Bash has no working heredocs — use the Write tool for multi-line file content,
  not `<<EOF`. Don't run PowerShell syntax (`$env:X`, `Get-ChildItem`) through bash —
  invoke it explicitly: `powershell -NoProfile -Command "..."`.
- Never use `sed`/`perl` in-place editing for path or escape-sequence rewriting — it
  has mangled bytes before. Use Python with explicit binary-safe reads/writes, and
  verify with `git diff` before committing. Quote paths defensively; filenames contain
  spaces.
- The Bitwarden CLI (`bw`) can hang indefinitely or return an empty password. Add a
  timeout and check for empty output before using a retrieved secret.
- Write files as UTF-8. Through PowerShell pass `-Encoding utf8` explicitly — its
  default varies by version and has produced mojibake in Japanese paths and content.

## Git Conventions

### Ignore patterns
Use `.git/info/exclude` for local-only ignore patterns (e.g. worktree directories).
Do not add personal/local entries to `.gitignore`.

### Branch naming
- Bug fixes: `bugfix/(name-of-thing)` — preferred; `fix/` is acceptable
- Features: `feat/(name-of-something)`
- Append date as `YYMMDD` suffix only to avoid name conflicts, e.g. `feat/(name)/260328`
- WIP branches: prefix with `wip/`, e.g. `wip/bugfix/(name)`, `wip/feat/(name)`

### Commit messages
- Follow conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `chore:`, `style:`, `docs:`
- WIP commits: use `WIP: <plain description>`, e.g. `WIP: fix auth token expiry`
  - No conventional prefix needed — WIP commits are rebased and reworded before merging

### Session-start commit check
At the start of a session, run `git diff HEAD --shortstat` to gauge pending changes.
If the total insertions + deletions is roughly 300 or more, ask the user whether they want to commit before proceeding.

### Repo root
Before a git command that writes (`add`, `commit`, `checkout`, `reset`, `rebase`, `push`),
confirm the target with `git rev-parse --show-toplevel`. The working directory is often
not the repo you mean — the chezmoi source, worktrees, and Unity projects all sit
adjacent to or nested near each other.

### Fetch before diverging
Always `git fetch origin` immediately before `rebase`, `merge`, or reasoning about
whether a branch has diverged — never rebase onto or reason about a stale local ref.
Never force-push without first showing `git log --oneline @{u}..` (what you'd overwrite)
and waiting for confirmation. Never `git checkout <other-branch> -- <paths>` into the
current working tree — create a worktree instead ([[using-git-worktrees]]).

### Rebasing
Before `git rebase --onto <target>`, always `git fetch` first and rebase onto the
fetched `origin/<target>` ref, not a possibly-stale local branch ref — unless the goal
is specifically to preserve local history as-is (e.g. deliberately rebasing onto a
known-stale local snapshot). Fetching is cheap; a stale local ref can silently diverge
from `origin/<target>` when someone else rebased or force-pushed it, producing a
result that looks correct locally but conflicts against the real upstream.

### Merge strategy
Rebase & fast-forward merge. Not squash merge.
GitHub does not sign commits merged this way — the branch commits land on `main` as-is,
keeping their original signature state.

### SSH signing fallback
If the signing agent is unavailable mid-commit, retry with `--no-gpg-sign` immediately.
Do not ask, do not investigate the cause — an unsigned WIP commit is never worth
interrupting the work for.
When the task is done, state plainly that the commits were made without signing.
Because the merge is rebase & ff, unsigned commits stay unsigned on `main`. Signing is
therefore reconciled once, at PR time, not during the work — see the `draft-pr` skill.

## Communication & Clarifying Intent

  If the subject of my request is vague — the *what* (which component, file,
  repo, page, element) isn't explicitly named — stop and ask before acting.
  Don't guess the noun and run with it; a vague subject is the most common;
  cause of wrong-approach rework.
  When I describe a change, expect me to name the exact subject first. If I
  don't, prompt me for it rather than inferring.
  Surface ambiguity early and cheaply: one clarifying question up front beats
  a discarded attempt.

When reporting, lead with the current conclusion and the main evidence for it. Do not
blur uncertainty; say specifically what is still unverified. For the shape of an
end-of-task report, see `## Reporting`.

When asking me for a decision, state the decision needed in one sentence before the
supporting facts — don't blend the two into one paragraph I have to untangle. Define
any abbreviation or internal shorthand on first use in a session.

## Executing a Plan

Before a run of tool calls, settle a mini plan: which calls, in what order, what each
one is for. Then execute it without narrating.

- Batch independent tool calls into a single message. Turn count is the cost — a call
  that does not depend on an earlier result must not wait for one.
- Put the intent in the call itself: a `#` comment in the shell command, a clear tool
  `description`. I read the calls, so prose between them is redundant.
- Do not post progress updates mid-run. Speak up only when something breaks, when a
  finding changes the plan, or when a decision is needed — then say it immediately
  rather than saving it for the final report.

## Explaining Code

When asked "how does X work" or for an explanation of behavior, answer in tiers and
pause for go-ahead after the first one, unless full depth was already asked for:
1. Concept — a few plain sentences on what it does, sourced from a spec/design doc
   when one exists, not inferred from UI resource strings or naming.
2. Boundaries — which module/layer owns what.
3. Call chain — the concrete file:line trace.

## Before Editing

- Before changing logic that depends on data shapes, expected values, or canonical sources: read the actual source first, state the assumption explicitly, and wait for confirmation before editing.
- For refactors spanning more than ~5 files: lay out the commit plan (what changes, in what order, verification step per commit) before touching any file.
- If the same kind of transformation spans 3 or more files, do not hand-edit. Write a script and verify it with the diff.
- Do not drop an existing abstraction (dataclass, base class, config object) as part of an unrelated refactor. If removing it looks necessary, stop and ask.
- Before editing a file under `~`, check whether it is a deployed copy rather than the
  source: `chezmoi source-path <file>` prints the source and exits 0 when managed, and
  errors when not. Edit the source and apply. Editing the deployed copy works until the
  next `chezmoi apply` silently reverts it.
- Do not modify code outside the change you were asked for. This includes adding
  comments to blocks you did not write or modify. Keep the changed-line count minimal.
- When something outside that scope looks like it should change, say so at the moment
  you notice it — not batched into the final report. Describe it, then continue the
  original work. Do not make the change unprompted.
- Split a destructive operation into three steps: produce a reviewable plan artifact
  (a CSV, a file list), execute it, then produce a measured report of what actually
  happened. Never fold the plan into the same step that executes it.
- Never commit secrets or credentials, SSH config included.
- For a document I own that you didn't create (a Notion page, an existing doc) — append
  or edit only the part asked about. Don't restructure or rewrite the rest unprompted.

## Code Style

- Reduce nesting. Prefer early return and `continue` over an arrow-shaped body.
- Extract recurring or meaningful values into named constants or enums. Keep
  self-explanatory one-off values inline — over-extraction is its own clutter. A value
  that comes from a spec (HTTP 200, a protocol magic byte, a file-format offset) gets a
  constant regardless of how many times it appears.
- For a parameter that selects behaviour, take an enum — or the language's nearest
  equivalent, such as a string-literal union — rather than a bool. `save(true)` tells
  the reader nothing at the call site.
- Keep members private unless the design needs external access. Widening visibility to
  internal or public is a design change, not a detail: ask before making it.
- A scratchpad or one-off script gets a short header — one or two lines on what it
  does, plus args, inputs and outputs. No background, no rationale, no account of why
  the session needed it.

## Running Code

Never launch or poll a long-running process (servers, training runs, watch tasks) via a blocking tool call — output capture stalls verification. Detach it, write logs to a file, and tail the file if you need to check progress. If it cannot be detached, build the code and give the user the exact command to run.

For analysis, conversion, or batch processing, write intermediate results to files and have each downstream step read them back. Re-running and verifying then cost a diff of the intermediate artifact instead of a full re-run.

## Reading Files

- Specify a range when calling Read unless the whole file is genuinely needed.
- For `docs/plans/*.md`, read the header block first, then pull in only the sections you need.
- Record what an image showed in text. Avoid re-reading the same image file; re-read only if it changed on disk.

## Searching

An empty result is not a finding. A search that returns nothing may have found absence,
or may have had a wrong path, a misremembered filename, or a pattern that could never
have matched.

Before reporting "there is no X", make the query prove it can return something: run it
against a term known to be present, or widen it one step and confirm the wider form
hits. Then report the absence, and say which check earned it.

When a file that git does not track goes missing, ask me where it went. Report what
is missing and what you observed (path, timestamps), then stop. Do not search the disk,
temp folders or the Recycle Bin for it, and hold edits to those files until I answer. I
usually know (a stash, a move). Recovering git-tracked content from history is fine.

## Consulting documentation

Before you consult documentation of non-local tools or libraries, perform a web search to
retrieve the correct URL of the documentation first, rather than inferring the URL directly.

## Verification

Decide "done" by running the commands in the project CLAUDE.md's `## Verification`
block: `quick` at a task close-out, `full` before a commit or PR. If a project has no
such block, ask what has to run for the work to count as successful and write the
answer into one, in the shape `welcome-claude` defines — `/init` on its own does not
produce it. Do not claim done before it exists. When you learn a command that block
does not list, add it there.

## Claiming Done

Before saying a UI or runtime change works, assert it against the running application —
DevTools for web, Unity MCP for game work — and say which assertion you ran. "The tests
pass" and "the code looks right" are not substitutes when the gap in question is between
the code and the running app.

This does not apply to pure logic changes where a test genuinely is the observation. It
applies where the thing that could be broken is the integration: wiring, injection, event
binding, device and scene state.

The same holds for a subagent's report of its own work. An agent cannot observe what it
was structurally unable to see, so treat its summary as a claim and check it against an
artifact it did not author — the filesystem, the console, the running app.

If the assertion is cheap to keep, make it a regression test rather than discarding it.

## Reporting

After executing a plan, close out under these headings, in this order. Adding further
headings is fine when they carry something the four do not.

- `# Done` — what was actually executed. Always present.
- `# Task Progress` — where the wider task now stands. Only when the work spans more
  than this turn.
- `# Things to discuss` — assumptions made while executing, and anything to confirm
  before the next task. Only when there is something; do not manufacture one to fill
  the heading.
- `# Next` — what comes next. Omit when nothing follows.

A question, a short answer, or a single-step change stays prose. These headings are for
the close-out of executed work.

## Code Review

When starting a review and no target (worktree, branch, or PR) is explicitly specified, ask for confirmation before proceeding.

## Subagents

- Dispatch a subagent when the work produces large output that main will not
  need to re-read (verification loops, log triage, cross-repo search).
- Keep it in the main session when the output will be referenced repeatedly.
- Default: return conclusions with file:line references, not raw content.
  Quote source only when the conclusion cannot stand without it.
- Read-only work (search, log triage, inventory) needs no confirmation.
- Before dispatching subagents that write code or edit files, main asks the user
  once, covering the whole batch. Within that batch a subagent executes without
  stopping to ask for routine permission.
- If a subagent hits a decision the batch approval did not cover, it surfaces it
  immediately — it does not guess and keep going, and it does not hold the
  question for its final report. A decision held is more expensive than a
  subagent that stops early, because work built on the wrong branch of it is
  thrown away.
- Delegate work whose result is cheap to verify. If checking the output costs about
  as much as producing it, do it in main instead. Claims a subagent cannot observe
  about itself — whether it was blocked, whether it waited — are never verifiable;
  do not build on them.
- Name the check before dispatching, not after: which artifact will show whether this
  worked, and what failure would look like in it. A check chosen after reading the
  report tends to be one the report already passes. On return, run it against that
  artifact, not against the agent's summary; if a load-bearing claim has no checkable
  artifact, say so rather than passing it through.
- For dispatching an agent purely to *check* a result, see `verify-before-claiming`.
- Commits are always made by main.
