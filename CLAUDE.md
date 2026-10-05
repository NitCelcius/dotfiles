# dotfiles

chezmoi source for the home directory. Global Claude Code instructions live in
`dot_claude/CLAUDE.md`; this file only covers working on the repo itself.

Load the `modifying-dotfiles` skill before changing any config in this repo.

## Verification

- **quick** (task close-out, aim for under 30s): `uv run --with pytest pytest -q`
- **full** (before a commit or PR): `uv run --with pytest pytest -q && chezmoi diff --no-pager --recursive ~/.claude`
- **Out of scope**: rendering of templates that call `bitwarden` (`dot_config/git/allowed_signers.tmpl`) — the local `bw` returns empty output, so only CI's `chezmoi apply --dry-run` with the mock `ci/bw` covers them.
