#!/usr/bin/env bash
# ~/.claude/hooks/play-sound.sh <name>
# Cross-platform (macOS / native Linux / WSL / Git Bash-MSYS-Cygwin on Windows) sound
# player for Claude Code hooks. Auto-detects the environment, so the same script,
# settings.json, and sounds/ folder can be reused as-is on any machine.

set -u
NAME="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILE="$SCRIPT_DIR/sounds/$NAME.wav"

[ -n "$NAME" ] || exit 0
[ -f "$FILE" ] || exit 0

if command -v afplay >/dev/null 2>&1; then
  # macOS
  afplay "$FILE" >/dev/null 2>&1 &
elif grep -qi microsoft /proc/version 2>/dev/null; then
  # WSL: hand the file off to the Windows host so it plays through the real audio device
  WIN_PATH=$(wslpath -w "$FILE" 2>/dev/null || echo "$FILE")
  powershell.exe -NoProfile -Command "(New-Object Media.SoundPlayer '$WIN_PATH').PlaySync()" >/dev/null 2>&1 &
elif command -v powershell.exe >/dev/null 2>&1; then
  # Native Windows via Git Bash / MSYS2 / Cygwin
  WIN_PATH=$(cygpath -w "$FILE" 2>/dev/null || echo "$FILE")
  powershell.exe -NoProfile -Command "(New-Object Media.SoundPlayer '$WIN_PATH').PlaySync()" >/dev/null 2>&1 &
elif command -v paplay >/dev/null 2>&1; then
  # Linux (PulseAudio / PipeWire-pulse)
  paplay "$FILE" >/dev/null 2>&1 &
elif command -v aplay >/dev/null 2>&1; then
  # Linux (ALSA)
  aplay -q "$FILE" >/dev/null 2>&1 &
fi

exit 0
