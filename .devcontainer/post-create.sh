#!/bin/bash
# Clones the read-only /src mount into ~/work and deploys its dot_claude to ~/.claude.
# Usage: post-create.sh  (run once by postCreateCommand; tests and hooks then run on the
# clone, so nothing in the container writes to the host checkout)
set -euo pipefail

SRC=/src
WORK="$HOME/work"

if [ ! -d "$WORK/.git" ]; then
  git clone -q "$SRC" "$WORK"
fi

# chezmoi renders templates that call `bw`; the CI mock answers them offline.
chmod +x "$WORK/ci/bw"
PATH="$WORK/ci:$PATH" chezmoi apply \
  --source "$WORK" \
  --destination "$HOME" \
  --no-pager \
  --force \
  "$HOME/.claude"
