# Workcell

Delegate bounded, independently verifiable tasks to isolated executor agents, and
escalate high-impact technical uncertainty to a read-only advisor. The goal is keeping
exploration and iteration out of the main agent's context — not parallelism.

- `team-executor` (Haiku, `isolation: worktree`) runs one bounded task in its own worktree.
- `team-advisor` (Opus, read-only) answers questions the main agent cannot resolve confidently.
- Records live at `~/.local/share/workcell` as analysis artifacts. They are not
  cross-device resume state; Git remains responsible for resuming work.

## Install

```
/plugin marketplace add NitCelcius/dotfiles
/plugin install workcell@nitcelcius
```

## Required setup

One settings entry, because executors read and update records that live outside the
project directory:

```json
{
  "permissions": {
    "additionalDirectories": ["~/.local/share/workcell"]
  }
}
```

Set `WORKCELL_ROOT` to put records elsewhere. The session start hook reports the
resolved root and the CLI's absolute path, so nothing needs to be on `PATH`.

## Optional

`worktree.baseRef: "head"` makes executor worktrees branch from your current local
HEAD. Under the default `fresh` they branch from `origin/<default-branch>`, so a local
checkpoint commit is not visible to an executor. Set it to `head` if you delegate on
top of uncommitted branch work. Note that it is a global setting: it governs every
worktree Claude Code creates, not only Workcell's.

## Activation

Delegation never starts on its own. `workcell-delegate` is marked
`disable-model-invocation`, so only you can trigger it with `/workcell-delegate`.

**The agents are not gated the same way.** Claude Code has no agent-level equivalent of
`disable-model-invocation`, so `team-executor` and `team-advisor` carry the restriction
in their descriptions only, which is advisory. If you want that gate enforced, add a
rule to your own `CLAUDE.md`:

> Do not invoke custom agents whose names start with `team-` unless the user explicitly
> invoked `/workcell-delegate` for the currently active plan.

## Known limitations

- Hooks invoke `python`, not `python3`. On systems where only `python3` exists,
  telemetry silently does nothing — the hook is fail-open by design.
- Executor worktrees are fresh checkouts and do not carry gitignored files. Projects
  that need them require a `.worktreeinclude`.
- `team-advisor` is denied the edit tools but can still run shell commands.
- `SubagentStop.agent_transcript_path` is undocumented. Subagent transcript archiving
  depends on it and may break without notice.

## Development

```
claude --plugin-dir <path-to-this-directory>
python -m unittest discover -s tests
```
