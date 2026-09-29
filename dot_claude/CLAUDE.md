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
  not `<<EOF`, even where a tool description suggests a heredoc.
- Never use `sed`/`perl` in-place editing for path or escape-sequence rewriting — it
  has mangled bytes before. Use Python with explicit binary-safe reads/writes, and
  verify with `git diff` before committing. Quote paths defensively; filenames contain
  spaces.
- The Bitwarden CLI (`bw`) can hang indefinitely or return an empty password. Add a
  timeout and check for empty output before using a retrieved secret.
- Write files as UTF-8. Through PowerShell pass `-Encoding utf8` explicitly — its
  default varies by version and has produced mojibake in Japanese paths and content.

## Git Conventions

Branch naming, local ignore patterns, fetching, rebasing, merging, and the signing
fallback live in the `git-workflow` skill.

### Commit messages
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

### Repo root
Before a git command that writes (`add`, `commit`, `checkout`, `reset`, `rebase`, `push`),
confirm the target with `git rev-parse --show-toplevel`. The working directory is often
not the repo you mean — the chezmoi source, worktrees, and Unity projects all sit
adjacent to or nested near each other.

### Rewriting others' state
Never force-push without first showing `git log --oneline @{u}..` (what you'd overwrite)
and waiting for confirmation. Never `git checkout <other-branch> -- <paths>` into the
current working tree — create a worktree instead ([[using-git-worktrees]]).

### Pull requests
Open every PR as a draft, and get user review of the body before `gh pr create` — with
or without `/draft-pr`. Body rules live in `~/.claude/skills/draft-pr/pr-body.md`; when
I correct a body, update that file.

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

Act as a brake. When an instruction of mine departs from the plan we agreed on, or
walks into a known mistake, say so once with your reason before following it. Known
mistakes include:
- an abstraction, dependency, or config knob added for a single use
- reimplementing something the codebase already provides
- patching a symptom at the call site when the cause is upstream
- editing a generated or deployed copy instead of its source
- hard-coding a machine-specific path, value, or secret
- swallowing an error so a failure looks like success
- mixing an unrelated change into the current commit or PR

This is optional — don't manufacture objections. When I invoke `/hear-my-plan`, just
listen.

## Executing a Plan

When a message from me arrives, plan the whole stretch until you next wait on me:
which calls, in what order, and where my input is needed. Then execute it without
narrating.

- Ask what needs my confirmation at the start of that stretch — before a long run of
  work, not midway. Collect the open questions and ask them together. Don't hold
  back a question to look autonomous.
- One approval covers every task it lists. Keep tasks small, but run them without
  stopping between them; I may extend the approval while work runs. Stop and ask
  only when an action falls outside what was approved.
- Two kinds of action are never covered implicitly and must be named in the
  approval: deleting a file I have not seen listed, and changing a public API or
  data contract. When one was named, do it, then list it in two places: under its
  own heading in the PR body, and at the very end of the message that hands the
  turn back to me.
- A newly discovered implementation detail is not a new decision for me. An
  invalidated requirement, a scope change, or a product tradeoff is. Presenting an
  unchanged design in new words does not need a fresh approval.
- In a bash call with five or more commands, put one command per line and separate
  logical groups with a blank line — not one long `&&` chain.
- Do not post progress updates mid-run. Speak up only when something breaks, when a
  finding changes the plan, or when a decision is needed — then say it immediately
  rather than saving it for the final report. When the harness asks what you are
  doing, one short line is enough.

## Before Editing

- Before changing logic that depends on data shapes, expected values, or canonical sources: read the actual source first, state the assumption explicitly, and wait for confirmation before editing. Two exceptions skip the wait, not the statement: in plan mode, put the assumption in the plan (approving the plan covers it); and when what settles the assumption is my prompt or our conversation, proceed.
- For refactors spanning more than ~5 files: lay out the commit plan (what changes, in what order, verification step per commit) before touching any file.
- If the same kind of transformation spans 3 or more files, do not hand-edit. Write a script and verify it with the diff.
- Do not drop an existing abstraction (dataclass, base class, config object) as part of an unrelated refactor. If removing it looks necessary, stop and ask.
- Before editing a file under `~`, check whether it is a deployed copy rather than the
  source: `chezmoi source-path <file>` prints the source and exits 0 when managed, and
  errors when not. Edit the source and apply. Editing the deployed copy works until the
  next `chezmoi apply` silently reverts it.
- Do not modify code outside the change you were asked for. This includes adding
  comments to blocks you did not write or modify. Keep the changed-line count minimal.
- When something outside that scope looks like it should change, ask me about it in
  chat at the moment you notice it — not batched into the final report. Describe it,
  then continue the original work. Do not make the change unprompted.
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
- A scratchpad or one-off script — including one written to a file in place of a
  heredoc — gets a short header: one or two lines on what it does, plus usage (args),
  inputs and outputs. No background, no rationale, no account of why
  the session needed it.

## Running Code

If a long-running process (server, training run, watch task) cannot be run in the background, build the code and give me the exact command to run.

For analysis, conversion, or batch processing, write intermediate results to files and have each downstream step read them back. Re-running and verifying then cost a diff of the intermediate artifact instead of a full re-run.

A verification or pipeline run must not overwrite tracked outputs. Write to a temp output path, or check `git status` afterwards and restore what the run changed.

## Reading Files

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

`verify-before-claiming` carries the tagging vocabulary for this rule.

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

When a turn produces a file for me to review (PR body, plan, report), give its absolute
path in the chat reply.

## Code Review

When starting a review and no target (worktree, branch, or PR) is explicitly specified, ask for confirmation before proceeding. Mechanics live in `review-my-diff` and the built-in `/code-review`.

## Subagents

When to dispatch, what a subagent returns, what needs approval, and how to check its
result live in the `dispatching-subagents` skill. Those criteria override the harness
default of spawning agents only on request: when they hold, dispatch without being asked.

- Pass `model` explicitly on every dispatch; an unspecified subagent inherits the
  main session's Opus, which is slow and costly. Default to Sonnet — iterative
  testing and coding are its job. Use Haiku only for read-only or judgment-free
  repeated operations, never where a decision or a change is needed. When Sonnet is
  struggling, hand the work to Opus.
- Only main integrates, cleans up history, and pushes. Subagents do not commit,
  except a Workcell executor inside an activated `/workcell-delegate` plan, which
  makes local WIP commits in its own worktree.

### Workcell gate

Do not invoke custom agents whose names start with `team-` unless the user explicitly
invoked `/workcell-delegate` for the currently active plan. Workcell authorization ends
when that plan completes, is abandoned, or changes to a substantially different Goal.
