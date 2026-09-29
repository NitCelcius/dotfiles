# dotfiles

Personal dotfiles managed with [chezmoi](https://www.chezmoi.io)

## Setup

On Windows or Linux, run:

```sh
chezmoi init --apply https://github.com/nitcelcius/dotfiles.git
```

Note, `~/.gitconfig.local` is loaded for machine-specific git config.

## Structure

| Path | Description |
|------|-------------|
| `dot_gitconfig.tmpl` | Git config |
| `.zshrc`, `.p10k.zsh` | Zsh + Powerlevel10k config (Linux) |
| `AppData/` | Windows-specific app config |
| `dot_claude/` | Claude Code config |
| `docs/` | Plans and evaluation records for this repo; not deployed |
| `ci/` | CI-only fixtures such as the mock `bw`; not deployed |

## Claude Code config

`dot_claude/` deploys to `~/.claude/`. Edit the source here and `chezmoi apply`;
an edit to the deployed copy is reverted by the next apply.

| Source | Deployed as |
|--------|-------------|
| `dot_claude/CLAUDE.md` | Global instructions for every project |
| `dot_claude/skills/` | Skills, including the Workcell plugin (`skills/workcell/`) |
| `dot_claude/verify-on-stop/` | Stop hook that runs a project's `quick` verification |
| `dot_claude/session-start-diff/` | SessionStart hook reporting uncommitted changes in the session's repo |
| `dot_claude/rm-junction-guard/` | PreToolUse hook that asks before a delete that a junction or shim relies on |

The `modifying-dotfiles` skill governs changes to this repo: branch first, edit the
source, keep private detail out, and log the reason for each change in Notion.

The root `CLAUDE.md` covers working on this repo and is not deployed. Workflow
regression scenarios for the global instructions live in
`docs/evals/claude-workflow-scenarios.md`.

## Verification

```sh
uv run --with pytest pytest -q                                          # quick
uv run --with pytest pytest -q && chezmoi diff --no-pager ~/.claude     # full, before a commit or PR
```

## Secrets

Secrets (SSH signing key) are stored in Bitwarden! Install [Bitwarden CLI](https://bitwarden.com/help/article/cli/) and log in to access secrets in templates.

## CI

GitHub Actions runs `chezmoi apply --dry-run` on every push to verify the templates render without errors. Note that you don't need to log into Bitwarden.

It also runs the pytest suite on Ubuntu. Windows is covered by running the suite locally.
