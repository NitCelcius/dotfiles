#!/usr/bin/env python3
"""Ask before a delete command reaches through a link or breaks a global shim; deny a
glob that deletes links until the command opts in.

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

It also asks when the deleted path runs through a folder named `node_modules`, a pnpm
store, `.venv` or `venv`, and a shim (.cmd, .ps1, .sh, extensionless) directly in
PNPM_HOME, %LOCALAPPDATA%\\pnpm, %APPDATA%\\npm or ~/.local/bin names a path inside it.

Either finding returns `ask`, so the user decides. Failing both, a delete that globs into
a folder (`rm -rf node_modules/*`) or empties one (cmd `del /s`, `Get-ChildItem`/`find`
piped into a delete) lists that folder's top level once. If a matching entry is a junction
or symlink, it returns `deny` with a caveat Claude reads. The same command with
`DELETE_IT_ANYWAY=1` set in it (`DELETE_IT_ANYWAY=1 rm ...`, `$env:DELETE_IT_ANYWAY=1; ...`)
runs, and the caveat goes to Claude as additionalContext instead. Deleting the folder by
name stays silent.

Unparseable input or an unresolvable path prints nothing and exits 0: the guard never
blocks on its own failure.
"""

from __future__ import annotations

import fnmatch
import glob
import json
import os
import re
import stat
import sys
from enum import Enum
from pathlib import Path

DELETE_VERBS = frozenset({"rm", "rmdir", "remove-item", "del", "erase", "ri", "rd"})
CMD_CONTENT_VERBS = frozenset({"del", "erase"})  # under cmd they empty a directory operand
CMD_SWITCH_VERBS = frozenset({"del", "erase", "rd"})  # take /s, /q; rmdir only under cmd
ENUMERATORS = frozenset({"get-childitem", "gci", "ls", "dir", "find"})
SHELLS = frozenset({"bash", "sh", "zsh", "pwsh", "powershell"})
WRAPPERS = frozenset({"sudo", "command", "exec", "nice", "time", "env", "xargs", "timeout", "builtin"})
# Wrapper options whose value is the next word (`nice -n 5 rm`, `env -C dir rm`).
WRAPPER_VALUE_OPTIONS = {
    "nice": frozenset({"-n", "--adjustment"}),
    "env": frozenset({"-C", "--chdir", "-u", "--unset"}),
    "timeout": frozenset({"-s", "--signal", "-k", "--kill-after"}),
}
WRAPPER_OPERANDS = {"timeout": 1}  # `timeout 10 rm ...`: the duration precedes the command
KEYWORDS = frozenset({"if", "then", "else", "elif", "while", "until", "do", "!"})
HERE_STRING = "<<<"  # `bash <<< 'script'`
PIPE_FEEDERS = frozenset({"echo", "printf"})  # `echo 'script' | bash`
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
ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")  # `NAME=value rm ...`
OVERRIDE_VAR = "DELETE_IT_ANYWAY"
OVERRIDE = re.compile(rf"(?:^|[\s;&|(])(?:\$env:)?{OVERRIDE_VAR}\s*=\s*['\"]?1(?!\w)", re.I)
MAX_NAMED_LINKS = 5

IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003  # junction
MAX_GLOB_MATCHES = 50
MAX_REFS = 10

# A delete through one of these names can take out what a global shim runs.
SHIM_FED_NAMES = frozenset({"node_modules", ".pnpm-store", "store", ".venv", "venv"})
SHIM_SUFFIXES = frozenset({".cmd", ".ps1", ".sh", ""})
SHIM_BASE_DIRS = ("%~dp0", "%dp0%", "$basedir")  # how pnpm/npm shims spell their own dir
MAX_SHIM_BYTES = 16 * 1024

Word = tuple[bool, str]  # (was_quoted, text)
Command = list[Word]


class Reach(Enum):
    ENTRY = "entry"  # the named path itself goes; a link there is removed as a link
    CONTENTS = "contents"  # what is inside the named path goes, so a link there is followed
    EMPTIES = "empties"  # as CONTENTS, and every entry directly inside is deleted too


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
    word_end = -1
    for match in TOKEN.finditer(command):
        dq, sq, op, bare = match.groups()
        if not op:
            word: Word = (not bare, bare or dq or sq or "")
            if command_words and match.start() == word_end:  # `X="a b"` is one word
                quoted, text = command_words.pop()
                word = (quoted and word[0], text + word[1])
            command_words.append(word)
            word_end = match.end()
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
    """(verb, args, nested script, under_cmd) after dropping `sudo`, `xargs -0`, `X=1`, `if` and the like."""
    while words:
        quoted, text = words[0]
        if not quoted and (ASSIGNMENT.match(text) or text in KEYWORDS):
            words = words[1:]
            continue
        wrapper = verb_of(text)
        if wrapper not in WRAPPERS:
            break
        words = words[1:]
        value_options = WRAPPER_VALUE_OPTIONS.get(wrapper, frozenset())
        while words and (words[0][1].startswith("-") or "=" in words[0][1]):
            words = words[2:] if words[0][1] in value_options else words[1:]
        words = words[WRAPPER_OPERANDS.get(wrapper, 0) :]
    if not words:
        return "", [], None, under_cmd
    verb, args = verb_of(words[0][1]), words[1:]
    if verb == "eval":
        return verb, [], rejoin(args), under_cmd
    for i, (quoted, text) in enumerate(args):
        if verb == "cmd" and text.lower() in ("/c", "/k"):
            return verb, [], rejoin(args[i + 1 :]), True
        if verb in SHELLS and not quoted and SCRIPT_FLAG.match(text):
            return verb, [], rejoin(args[i + 1 :]), False
        if verb in SHELLS and not quoted and text.startswith(HERE_STRING):
            script = text[len(HERE_STRING) :] or (args[i + 1][1] if i + 1 < len(args) else "")
            return verb, [], script, False
    return verb, args, None, under_cmd


def stage_commands(pipeline: list[list[Command]], under_cmd: bool) -> list[tuple[int, str, Command, str | None, bool]]:
    """(stage index, verb, args, nested script, under_cmd) per command of a pipeline.

    A shell fed by `echo`/`printf` in the stage before (`echo 'rm -rf x' | bash`) runs
    the echoed text, so that text becomes its nested script.
    """
    found: list[tuple[int, str, Command, str | None, bool]] = []
    fed: str | None = None
    for index, stage in enumerate(pipeline):
        piped, fed = fed, None
        for words in stage:
            verb, args, nested, nested_under_cmd = unwrap(words, under_cmd)
            if nested is None and piped is not None and verb in SHELLS and not positional(args, switches=False):
                nested, nested_under_cmd = piped, False
            if verb in PIPE_FEEDERS:
                fed = " ".join(text for quoted, text in args if quoted or not text.startswith("-"))
            found.append((index, verb, args, nested, nested_under_cmd))
    return found


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
    if under_cmd and verb in CMD_CONTENT_VERBS:
        recursive = any(not quoted and text.lower() == "/s" for quoted, text in args)
        reach = Reach.EMPTIES if recursive else Reach.CONTENTS
        return [(raw, reach) for raw in positional(args, switches)]
    return [
        (raw, Reach.CONTENTS if has_trailing_separator(raw) else Reach.ENTRY)
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
        for index, verb, args, nested, nested_under_cmd in stage_commands(pipeline, under_cmd):
            if nested is not None:
                found.extend(operands(nested, nested_under_cmd))
            elif verb in DELETE_VERBS:
                found.extend(delete_operands(verb, args, nested_under_cmd))
                last_delete_stage = index
            elif verb in ENUMERATORS:
                sources.extend((index, path) for path in enumerated_paths(verb, args))
        # A delete fed by an enumerator removes what the enumerator listed inside its path.
        found.extend((path, Reach.EMPTIES) for index, path in sources if index < last_delete_stage)
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


def shim_dirs() -> list[str]:
    candidates = [
        os.environ.get("PNPM_HOME", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "pnpm"),
        os.path.join(os.environ.get("APPDATA", ""), "npm"),
        os.path.join(os.path.expanduser("~"), ".local", "bin"),
    ]
    seen: dict[str, str] = {}
    for directory in candidates:
        if os.path.isabs(directory) and os.path.isdir(directory):
            seen.setdefault(os.path.normcase(os.path.abspath(directory)), directory)
    return list(seen.values())


def shim_texts() -> list[tuple[str, str]]:
    """(path, lowercased text) of every shim directly inside a shim directory."""
    shims: list[tuple[str, str]] = []
    for directory in shim_dirs():
        try:
            entries = list(os.scandir(directory))
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith(".") or Path(entry.name).suffix.lower() not in SHIM_SUFFIXES:
                continue
            try:
                if not entry.is_file(follow_symlinks=False) or entry.stat().st_size > MAX_SHIM_BYTES:
                    continue
                data = Path(entry.path).read_bytes()
            except OSError:
                continue
            if b"\0" not in data:
                shims.append((entry.path, data.decode("utf-8", errors="ignore").lower()))
    return shims


def mention_pattern(target: str, shim_dir: str) -> re.Pattern[str]:
    """Spellings of target a shim could use: absolute, Git Bash, and from the shim's own dir.

    A relative spelling counts only right after the shim's base-dir token, so
    `%~dp0\\global\\...\\node_modules` does not match `node_modules` beside the shim.
    """
    forms = {target, target.replace("\\", "/")}
    drive = re.match(r"^([a-zA-Z]):[\\/]", target)
    if drive:
        forms.add(f"/{drive.group(1).lower()}/" + target[3:].replace("\\", "/"))
    try:
        rel = os.path.relpath(target, shim_dir)
    except ValueError:  # different drive
        rel = ""
    if rel and rel != os.curdir and not rel.startswith(".."):
        for base in SHIM_BASE_DIRS:
            forms.update({f"{base}\\{rel}", f"{base}/{rel.replace(os.sep, '/')}"})
    alternatives = "|".join(re.escape(form.lower()) for form in forms)
    return re.compile(rf"(?:{alternatives})(?=[\\/\"'\s]|$)")


def resolved(raw: str, cwd: str) -> list[tuple[str, str]]:
    """(full path, start of the spelled-out part) for each path `raw` names."""
    path = expand(raw)
    if path is None:
        return []
    relative = not os.path.isabs(path)
    joined = os.path.join(cwd, path) if relative else path
    matches = glob.glob(joined)[:MAX_GLOB_MATCHES] if GLOB_CHARS.search(joined) else [joined]
    return [(full, spelled_out_start(full, cwd, relative)) for full in map(os.path.normpath, matches)]


def references(raw: str, reach: Reach, cwd: str, shims: list[tuple[str, str]] | None) -> tuple[list[str], list[tuple[str, str]] | None]:
    """Report lines for `raw`, plus the shim texts once they have been read."""
    lines: list[str] = []
    for full, start in resolved(raw, cwd):
        link = first_link(full, start, reach)
        if link:
            lines.append(f"`{raw}` reaches through {link_kind(link)} {link} -> {os.path.realpath(link)}")
        names = {part.lower() for part in Path(full).parts}
        if not names & SHIM_FED_NAMES:
            continue
        if shims is None:
            shims = shim_texts()
        for shim, text in shims:
            if mention_pattern(full, os.path.dirname(shim)).search(text):
                lines.append(f"`{raw}` removes what shim {shim} runs")
    return lines, shims


def emptied_folder(raw: str, reach: Reach, cwd: str) -> tuple[str, str] | None:
    """(folder, entry pattern) when the delete takes every matching entry directly inside a folder."""
    path = expand(raw)
    if path is None:
        return None
    full = os.path.normpath(os.path.join(cwd, path))
    if reach is Reach.EMPTIES:
        return (full, "*") if not GLOB_CHARS.search(full) and os.path.isdir(full) else None
    folder, pattern = os.path.split(full)
    if GLOB_CHARS.search(pattern) and not GLOB_CHARS.search(folder) and os.path.isdir(folder):
        return folder, pattern
    return None


def linked_entries(folder: str, pattern: str) -> list[str]:
    """Names of junctions and symlinks directly inside folder that match pattern (one scandir)."""
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return []
    return [entry.name for entry in entries if fnmatch.fnmatch(entry.name, pattern) and link_kind(entry.path)]


def caveats(command: str, cwd: str) -> list[tuple[str, list[str]]]:
    """(operand, link names) for each glob or emptying delete whose folder holds links."""
    found: list[tuple[str, list[str]]] = []
    for raw, reach in operands(command):
        target = emptied_folder(raw, reach, cwd)
        links = linked_entries(*target) if target else []
        if links:
            found.append((raw, links))
    return found


def caveat_lines(found: list[tuple[str, list[str]]]) -> str:
    lines = []
    for raw, links in found:
        named = ", ".join(links[:MAX_NAMED_LINKS]) + (", ..." if len(links) > MAX_NAMED_LINKS else "")
        lines.append(f"`{raw}` deletes {len(links)} junctions/symlinks by listing their folder: {named}")
    return "\n".join(lines)


def emit(output: dict[str, str]) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **output}}))


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
    shims: list[tuple[str, str]] | None = None  # read on first need, at most once
    try:
        for raw, reach in operands(command):
            lines, shims = references(raw, reach, cwd, shims)
            refs.extend(line for line in lines if line not in refs)
        found = [] if refs else caveats(command, cwd)
    except OSError:
        return 0
    if refs:
        reason = "This delete removes more than the path it names:\n- " + "\n- ".join(refs[:MAX_REFS])
        emit({"permissionDecision": "ask", "permissionDecisionReason": reason})
        return 0
    if not found:
        return 0

    if OVERRIDE.search(command):
        note = f"{OVERRIDE_VAR}=1 was set, so this ran:\n{caveat_lines(found)}\nCheck the links' targets still exist."
        emit({"additionalContext": note})
        return 0
    reason = (
        f"{caveat_lines(found)}\n"
        "rm and Remove-Item removed only the links in testing (junctions, PowerShell 5.1.26100 and "
        "7.6.6), but symlinks and older PowerShell may follow them. Delete the folder by name "
        f"instead, or if this is intended, rerun with {OVERRIDE_VAR}=1: "
        f"`{OVERRIDE_VAR}=1 <command>` in Bash, `$env:{OVERRIDE_VAR}=1; <command>` in PowerShell."
    )
    emit({"permissionDecision": "deny", "permissionDecisionReason": reason})
    return 0


if __name__ == "__main__":
    sys.exit(main())
