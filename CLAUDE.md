# dotfiles

chezmoi source for the home directory. Global Claude Code instructions live in
`dot_claude/CLAUDE.md`; this file only covers working on the repo itself.

## Verification

- **quick** (task close-out, aim for under 30s): `uv run python dot_claude/verify-on-stop/verify_on_stop.py --selftest && uv run python dot_claude/verify-on-stop/test_verify_on_stop.py && uv run python dot_claude/session-start-diff/test_session_start_diff.py`
- **full** (before a commit or PR): `uv run python dot_claude/verify-on-stop/verify_on_stop.py --selftest && uv run python dot_claude/verify-on-stop/test_verify_on_stop.py && uv run python dot_claude/session-start-diff/test_session_start_diff.py && chezmoi diff --no-pager ~/.claude`
- **Out of scope**: rendering of templates that call `bitwarden` (`dot_config/git/allowed_signers.tmpl`) — the local `bw` returns empty output, so only CI's `chezmoi apply --dry-run` with the mock `ci/bw` covers them.
