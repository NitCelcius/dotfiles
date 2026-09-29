#!/usr/bin/env python3
"""Ask before a delete command reaches through a junction or symlink into its target.

Wired as a PreToolUse hook (matcher `Bash|PowerShell`). Reads the hook payload on
stdin for `tool_input.command` and `cwd`. A command with no delete verb (`rm`,
`rmdir`, `Remove-Item`, `del`, `erase`, `ri`, `rd`) exits at once with no output.

Naming a link to delete it (`rm -rf link`, `Remove-Item -Recurse link`, `rd /s link`)
removes only the link, so that stays silent. A delete that goes through a link removes
files inside its target, so it asks:

  - a path component before the last is a link: `rm -rf link/sub`, `rm -rf link/*`
  - the path names a link with a trailing separator: `rm -rf link/`
  - cmd's `del`/`erase`, which delete the files inside a directory operand
  - a `Get-ChildItem`/`find` whose results are piped into a delete verb

Only the path components the command spells out are checked, not those of `cwd`.
Unparseable input or an unresolvable path prints nothing and exits 0: the guard never
blocks on its own failure.
"""

from __future__ import annotations

import glob
import json
import os
import re
import stat
import sys
from enum import Enum

DELETE_VERBS = frozenset({"rm", "rmdir", "remove-item", "del", "erase", "ri", "rd"})
CMD_CONTENT_VERBS = frozenset({"del", "erase"})  # under cmd they empty a directory operand
CMD_SWITCH_VERBS = frozenset({"del", "erase", "rd"})  # take /s, /q; rmdir only under cmd
ENUMERATORS = frozenset({"get-childitem", "gci", "ls", "dir", "find"})
SHELLS = frozenset({"bash", "sh", "zsh", "pwsh", "powershell"})
WRAPPERS = frozenset({"sudo", "command", "exec", "nice", "time", "env", "xargs"})
VALUE_PARAMS = frozenset({"-include", "-exclude", "-filter", "-depth"})

# Cheap pre-filter for the common case; the lexer below does the real work.
DELETE_HINT = re.compile(r"(?<![\w-])(?:rm|rmdir|remove-item|del|erase|ri|rd)(?![\w-])", re.I)
TOKEN = re.compile(r'"([^"]*)"|\'([^\']*)\'|(\|\||&&|[;&|\n{}()])|([^\s"\';&|{}()]+)')
STATEMENT_ENDS = frozenset({";", "&&", "||", "&", "\n"})
BLOCK_MARKS = frozenset({"{", "}", "(", ")"})
SCRIPT_FLAG = re.compile(r"^-(?:l?c|com(?:m(?:a(?:n(?:d)?)?)?)?)$", re.I)  # bash -c, pwsh -Command
CMD_SWITCH = re.compile(r"^/[a-zA-Z?](?::\S*)?$")
GIT_BASH_DRIVE = re.compile(r"^/([a-zA-Z])(?:/|$)")
GLOB_CHARS = re.compile(r"[*?\[]")

IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003  # junction
MAX_GLOB_MATCHES = 50
MAX_REFS = 10

Word = tuple[bool, str]  # (was_quoted, text)
Command = list[Word]


class Reach(Enum):
    ENTRY = "entry"  # the named path itself goes; a link there is removed as a link
    CONTENTS = "contents"  # what is inside the named path goes, so a link there is followed


def link_kind(path: str) -> str | None:
    try:
        st = os.lstat(path)
    except OSError:
        return None
    if stat.S_ISLNK(st.st_mode):
        return "symlink"
    if getattr(st, "st_reparse_tag", 0) == IO_REPARSE_TAG_MOUNT_POINT:
        return "junction"
    return None


def verb_of(token: str) -> str:
    name = re.split(r"[\\/]", token)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def pipelines(command: str) -> list[list[list[Command]]]:
    """Group words into pipelines of stages of commands, splitting outside quotes.

    `;`, `&&`, `||`, `&` and newlines end a pipeline, `|` ends a stage, and braces or
    parentheses start a new command within the stage (`ForEach-Object { Remove-Item }`).
    """
    result: list[list[list[Command]]] = []
    pipeline: list[list[Command]] = []
    stage: list[Command] = []
    command_words: Command = []
    for dq, sq, op, bare in TOKEN.findall(command):
        if not op:
            command_words.append((not bare, bare or dq or sq))
            continue
        if command_words:
            stage.append(command_words)
            command_words = []
        if op in BLOCK_MARKS:
            continue
        if stage:
            pipeline.append(stage)
            stage = []
        if op in STATEMENT_ENDS and pipeline:
            result.append(pipeline)
            pipeline = []
    if command_words:
        stage.append(command_words)
    if stage:
        pipeline.append(stage)
    if pipeline:
        result.append(pipeline)
    return result


def rejoin(words: Command) -> str:
    if len(words) == 1 and words[0][0]:
        return words[0][1]
    return " ".join(f'"{text}"' if quoted else text for quoted, text in words)


def unwrap(words: Command, under_cmd: bool) -> tuple[str, Command, str | None, bool]:
    """(verb, args, nested script, under_cmd) after dropping `sudo`, `xargs -0` and the like."""
    while words and verb_of(words[0][1]) in WRAPPERS:
        words = words[1:]
        while words and (words[0][1].startswith("-") or "=" in words[0][1]):
            words = words[1:]
    if not words:
        return "", [], None, under_cmd
    verb, args = verb_of(words[0][1]), words[1:]
    for i, (quoted, text) in enumerate(args):
        if verb == "cmd" and text.lower() in ("/c", "/k"):
            return verb, [], rejoin(args[i + 1 :]), True
        if verb in SHELLS and not quoted and SCRIPT_FLAG.match(text):
            return verb, [], rejoin(args[i + 1 :]), False
    return verb, args, None, under_cmd


def positional(args: Command, switches: bool) -> list[str]:
    """Path arguments: flags, their values and cmd `/x` switches dropped."""
    found: list[str] = []
    skip_value = False
    for quoted, text in args:
        if skip_value:
            skip_value = False
            continue
        if not quoted and text.startswith("-"):
            skip_value = text.lower() in VALUE_PARAMS
            continue
        if not quoted and switches and CMD_SWITCH.match(text):
            continue
        found.append(text)
        if not quoted and "," in text:  # PowerShell array: Remove-Item a,b
            found.extend(part for part in text.split(",") if part)
    return found


def has_trailing_separator(raw: str) -> bool:
    return raw.endswith(("/", "\\")) and raw.rstrip("/\\") not in ("", ".") and not raw.endswith(":\\")


def delete_operands(verb: str, args: Command, under_cmd: bool) -> list[tuple[str, Reach]]:
    switches = verb in CMD_SWITCH_VERBS or (under_cmd and verb == "rmdir")
    empties = under_cmd and verb in CMD_CONTENT_VERBS
    return [
        (raw, Reach.CONTENTS if empties or has_trailing_separator(raw) else Reach.ENTRY)
        for raw in positional(args, switches)
    ]


def enumerated_paths(verb: str, args: Command) -> list[str]:
    if verb != "find":
        return positional(args, switches=False)
    paths: list[str] = []
    for _, text in args:
        if text in ("-H", "-L", "-P"):
            continue
        if text.startswith(("-", "!", "(")):
            break
        paths.append(text)
    return paths


def operands(command: str, under_cmd: bool = False) -> list[tuple[str, Reach]]:
    """Every path a delete in the command removes, with how far the delete reaches."""
    found: list[tuple[str, Reach]] = []
    for pipeline in pipelines(command):
        sources: list[tuple[int, str]] = []
        last_delete_stage = -1
        for index, stage in enumerate(pipeline):
            for words in stage:
                verb, args, nested, nested_under_cmd = unwrap(words, under_cmd)
                if nested is not None:
                    found.extend(operands(nested, nested_under_cmd))
                elif verb in DELETE_VERBS:
                    found.extend(delete_operands(verb, args, nested_under_cmd))
                    last_delete_stage = index
                elif verb in ENUMERATORS:
                    sources.extend((index, path) for path in enumerated_paths(verb, args))
        # A delete fed by an enumerator removes what the enumerator listed inside its path.
        found.extend((path, Reach.CONTENTS) for index, path in sources if index < last_delete_stage)
    return found


def expand(raw: str) -> str | None:
    path = os.path.expandvars(os.path.expanduser(raw))
    if "$" in path or "%" in path:
        return None
    drive = GIT_BASH_DRIVE.match(path)
    if drive and os.name == "nt":
        path = f"{drive.group(1)}:{path[2:] or '/'}"
    return path


def spelled_out_start(full: str, cwd: str, relative: bool) -> str:
    """Directory above the part of `full` the command spelled out."""
    anchor = os.path.splitdrive(full)[0] + os.sep
    if not relative:
        return anchor
    try:
        return os.path.commonpath([full, os.path.normpath(cwd)])
    except ValueError:  # different drive
        return anchor


def first_link(full: str, start: str, reach: Reach) -> str | None:
    rel = os.path.relpath(full, start)
    parts = [] if rel == os.curdir else rel.split(os.sep)
    if reach is Reach.ENTRY:
        parts = parts[:-1]
    current = start
    for part in parts:
        current = os.path.join(current, part)
        if link_kind(current):
            return current
    return None


def crossings(raw: str, reach: Reach, cwd: str) -> list[str]:
    """The links a delete of `raw` passes through, as report lines."""
    path = expand(raw)
    if path is None:
        return []
    relative = not os.path.isabs(path)
    joined = os.path.join(cwd, path) if relative else path
    matches = glob.glob(joined)[:MAX_GLOB_MATCHES] if GLOB_CHARS.search(joined) else [joined]
    lines: list[str] = []
    for match in matches:
        full = os.path.normpath(match)
        link = first_link(full, spelled_out_start(full, cwd, relative), reach)
        if not link:
            continue
        line = f"`{raw}` reaches through {link_kind(link)} {link} -> {os.path.realpath(link)}"
        if line not in lines:
            lines.append(line)
    return lines


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload["tool_input"]["command"]
        cwd = payload.get("cwd") or os.getcwd()
    except (ValueError, KeyError, TypeError, AttributeError):
        return 0
    if not isinstance(command, str) or not isinstance(cwd, str) or not DELETE_HINT.search(command):
        return 0

    refs: list[str] = []
    try:
        for raw, reach in operands(command):
            refs.extend(line for line in crossings(raw, reach, cwd) if line not in refs)
    except OSError:
        return 0
    if not refs:
        return 0

    reason = "This delete reaches through a junction or symlink and would remove files in its target:\n- "
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": reason + "\n- ".join(refs[:MAX_REFS]),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
