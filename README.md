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

## Secrets

Secrets (SSH signing key) are stored in Bitwarden! Install [Bitwarden CLI](https://bitwarden.com/help/article/cli/) and log in to access secrets in templates.

## CI

GitHub Actions runs `chezmoi apply --dry-run` on every push to verify the templates render without errors. Note that you don't need to log into Bitwarden.
