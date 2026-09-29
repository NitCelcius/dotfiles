#!/usr/bin/env python3
"""Ask before a delete command removes something that junctions or shims depend on.

Wired as a PreToolUse hook (matcher `Bash|PowerShell`). Reads the hook payload on
stdin for `tool_input.command` and `cwd`. A command with no delete verb (`rm`,
`rmdir`, `Remove-Item`, `del`, `erase`, `ri`, `rd`; `git rm` excluded) exits at once
with no output. For a delete verb, each target path is resolved against `cwd` and
checked for:

  - the target is itself a junction or symlink
  - the target contains a junction or symlink a recursive delete could traverse
  - a junction or symlink elsewhere points into the target, or a shim script
    (.cmd, .ps1, .sh, extensionless) mentions its path. Only the target's parent,
    PNPM_HOME, %LOCALAPPDATA%\\pnpm and ~/.local are searched, to a shallow depth.

A hit prints a PreToolUse `ask` decision naming each reference. Otherwise nothing is
printed. Unparseable input, an unresolvable path or a slow search prints nothing and
exits 0: the guard never blocks on its own failure.
"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
import time
from collections.abc import Iterator
from pathlib import Path

DELETE_VERBS = frozenset({"rm", "rmdir", "remove-item", "del", "erase", "ri", "rd"})
# Cheap pre-filter for the common case; the tokenizer below does the real work.
DELETE_HINT = re.compile(r"(?<![\w-])(?:rm|rmdir|remove-item|del|erase|ri|rd)(?![\w-])", re.I)
SEGMENT_SPLIT = re.compile(r"[;|&\n]+")
TOKEN = re.compile(r'"([^"]*)"|\'([^\']*)\'|(\S+)')
CMD_SWITCH = re.compile(r"^/[a-zA-Z?]$")
GIT_BASH_DRIVE = re.compile(r"^/([a-zA-Z])(?:/|$)")
GLOB_CHARS = re.compile(r"[*?\[]")

IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003  # junction
SHIM_SUFFIXES = frozenset({".cmd", ".ps1", ".sh", ""})
MAX_SHIM_BYTES = 16 * 1024
MAX_GLOB_MATCHES = 50
MAX_REFS = 10
PARENT_DEPTH = 2
NAMED_ROOT_DEPTH = 3
CONTENT_DEPTH = 64
DEADLINE_SECONDS = 6.0


def is_link(entry: os.DirEntry[str]) -> bool:
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return getattr(st, "st_reparse_tag", 0) == IO_REPARSE_TAG_MOUNT_POINT


def path_is_link(path: str) -> bool:
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return getattr(st, "st_reparse_tag", 0) == IO_REPARSE_TAG_MOUNT_POINT


def within(path: str, root: str) -> bool:
    path, root = os.path.normcase(path), os.path.normcase(root)
    return path == root or path.startswith(root.rstrip("\\/") + os.sep)


def walk(root: str, max_depth: int, deadline: float, prune: str | None = None) -> Iterator[os.DirEntry[str]]:
    """Yield every entry under root without following links; stop at the deadline."""
    stack = [(root, 1)]
    while stack:
        if time.monotonic() > deadline:
            return
        directory, depth = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        for entry in entries:
            yield entry
            if depth >= max_depth or is_link(entry):
                continue
            if prune and within(entry.path, prune):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append((entry.path, depth + 1))
            except OSError:
                continue


def tokens(segment: str) -> list[tuple[str, bool]]:
    """Split on whitespace, keeping quoted runs whole. Returns (text, was_quoted)."""
    return [(dq or sq or bare, bool(dq or sq)) for dq, sq, bare in TOKEN.findall(segment)]


def verb_of(token: str) -> str:
    name = re.split(r"[\\/]", token)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def raw_targets(command: str) -> list[str]:
    """Arguments of every delete verb in the command, quotes stripped, flags dropped."""
    found: list[str] = []
    for segment in SEGMENT_SPLIT.split(command):
        toks = tokens(segment)
        if not toks or verb_of(toks[0][0]) == "git":
            continue
        for i, (text, quoted) in enumerate(toks):
            if quoted and " " in text and DELETE_HINT.search(text):
                found.extend(raw_targets(text))  # powershell -c "Remove-Item ..."
            if verb_of(text) not in DELETE_VERBS:
                continue
            for arg, _ in toks[i + 1 :]:
                if arg.startswith("-") or CMD_SWITCH.match(arg):
                    continue
                found.append(arg)
                if "," in arg:
                    found.extend(part for part in arg.split(",") if part)
    return found


def resolve(raw: str, cwd: str) -> list[str]:
    path = os.path.expandvars(os.path.expanduser(raw))
    if "$" in path or "%" in path:
        return []
    drive = GIT_BASH_DRIVE.match(path)
    if drive and os.name == "nt":
        path = f"{drive.group(1)}:{path[2:] or '/'}"
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    if GLOB_CHARS.search(path):
        import glob

        matches = glob.glob(path)[:MAX_GLOB_MATCHES]
    else:
        matches = [path]
    return [os.path.normpath(m) for m in matches if os.path.lexists(m)]


def search_roots(targets: list[str]) -> list[tuple[str, int]]:
    """(directory, depth) pairs, deduplicated; the deeper depth wins."""
    roots = [(os.path.dirname(t), PARENT_DEPTH) for t in targets]
    if os.environ.get("PNPM_HOME"):
        roots.append((os.environ["PNPM_HOME"], NAMED_ROOT_DEPTH))
    if os.environ.get("LOCALAPPDATA"):
        roots.append((os.path.join(os.environ["LOCALAPPDATA"], "pnpm"), NAMED_ROOT_DEPTH))
    roots.append((os.path.join(os.path.expanduser("~"), ".local"), NAMED_ROOT_DEPTH))
    seen: dict[str, tuple[str, int]] = {}
    for root, depth in roots:
        if not os.path.isdir(root):
            continue
        key = os.path.normcase(os.path.abspath(root))
        if key not in seen or seen[key][1] < depth:
            seen[key] = (root, depth)
    return list(seen.values())


def mention_forms(target: str, shim_dir: str) -> list[str]:
    """Spellings of target a shim could use: absolute, Git Bash, and relative to the shim."""
    forms = {target, target.replace("\\", "/")}
    drive = re.match(r"^([a-zA-Z]):[\\/]", target)
    if drive:
        forms.add(f"/{drive.group(1).lower()}/" + target[3:].replace("\\", "/"))
    try:
        rel = os.path.relpath(target, shim_dir)
    except ValueError:  # different drive
        rel = ""
    if rel and not rel.startswith(".."):
        # Leading separator, as in `$basedir/pkg`, so a bare name in a .gitignore misses.
        forms.update({"\\" + rel, "/" + rel.replace("\\", "/")})
    return [f.lower() for f in forms]


def shim_mentions(entry: os.DirEntry[str], target: str) -> bool:
    if entry.name.startswith(".") or Path(entry.name).suffix.lower() not in SHIM_SUFFIXES:
        return False
    try:
        if not entry.is_file(follow_symlinks=False) or entry.stat().st_size > MAX_SHIM_BYTES:
            return False
        data = Path(entry.path).read_bytes()
    except OSError:
        return False
    if b"\0" in data:
        return False
    text = data.decode("utf-8", errors="ignore").lower()
    return any(form in text for form in mention_forms(target, os.path.dirname(entry.path)))


def find_references(targets: list[str], deadline: float) -> list[str]:
    refs: list[str] = []

    def full() -> bool:
        return len(refs) >= MAX_REFS

    for target in targets:
        if path_is_link(target):
            refs.append(f"{target} is itself a junction or symlink")
    for target in targets:
        if path_is_link(target) or not os.path.isdir(target):
            continue
        for entry in walk(target, CONTENT_DEPTH, deadline):
            if full():
                return refs
            if is_link(entry):
                refs.append(f"{target} contains a junction or symlink: {entry.path}")

    real = {t: (t if path_is_link(t) else os.path.realpath(t)) for t in targets}
    for root, depth in search_roots(targets):
        for entry in walk(root, depth, deadline):
            if full():
                return refs
            for target in targets:
                if within(entry.path, target):
                    continue
                if is_link(entry):
                    if within(os.path.realpath(entry.path), real[target]):
                        refs.append(f"{entry.path} (junction or symlink) points into {target}")
                elif shim_mentions(entry, target):
                    refs.append(f"shim {entry.path} mentions {target}")
    return refs


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload["tool_input"]["command"]
        cwd = payload.get("cwd") or os.getcwd()
    except (ValueError, KeyError, TypeError, AttributeError):
        return 0
    if not isinstance(command, str) or not DELETE_HINT.search(command):
        return 0

    deadline = time.monotonic() + DEADLINE_SECONDS
    try:
        targets = sorted({p for raw in raw_targets(command) for p in resolve(raw, cwd)})
        refs = find_references(targets, deadline) if targets else []
    except OSError:
        return 0
    if not refs:
        return 0

    reason = "This delete may break things that depend on the target:\n- " + "\n- ".join(refs)
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
