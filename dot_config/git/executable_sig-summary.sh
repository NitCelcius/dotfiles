#!/bin/sh
# post-commit hook, registered globally as hook.sig-summary in ~/.gitconfig.
# Prints a one-line signature status for the new HEAD.
short=$(git rev-parse --short HEAD)
case $(git log -1 --format=%G? HEAD) in
	G) echo "[sig] $short: signed OK" ;;
	N) echo "[sig] $short: NOT signed" ;;
	*) echo "[sig] $short: signed but NOT verified" ;;
esac
