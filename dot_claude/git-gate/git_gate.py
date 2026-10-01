#!/usr/bin/env python3
"""Gate the git deletes and pushes that static permission rules cannot judge.

Wired as a PreToolUse hook (matcher `Bash|PowerShell`). Reads the hook payload on
stdin for `tool_input.command` and `cwd`, and splits the command with the lexer in
`rm-junction-guard`, tracking `cd`/`Set-Location` and `git -C` to find each repo.

  - `git branch -D` (or `-d` with `-f`) asks only for a branch that has commits on no
    remote-tracking ref and still has a remote counterpart (an upstream or a same-name
    remote branch). A local-only branch, or one whose commits are all pushed, stays
    silent; `permissions.allow` then lets it run.
  - `git push` with a `+refspec` is a force push and is denied, like `--force`.
  - `git push` with a `:refspec` or `--delete`/`-d`, in any argument order, asks.

With `--unattended` (registered by the `unattended-run` skill) every one of those, and
every command a live `permissions.ask` rule matches, is denied with a reason instead,
so an unattended run skips the action and keeps going rather than waiting on a prompt.

Outside `--unattended`, a command with no `git` exits at once with no output.
Unparseable input prints nothing; a branch whose state cannot be read asks, as the old
static rule did.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "rm-junction-guard"))
from rm_junction_guard import expand, pipelines, unwrap  # noqa: E402

UNATTENDED_FLAG = "--unattended"
GIT_HINT = re.compile(r"(?<![\w-])git(?![\w-])", re.I)
MISSING_REF = 1  # `git rev-parse --verify --quiet` exit code for a ref that does not exist
CD_VERBS = frozenset({"cd", "set-location", "sl", "chdir", "pushd"})
GIT_VALUE_OPTIONS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"})
RULE = re.compile(r"^(Bash|PowerShell)\((.*)\)$", re.S)
GIT_TIMEOUT = 5
MAX_REASONS = 10

Words = list[tuple[bool, str]]


class Decision(Enum):
    ASK = "ask"
    DENY = "deny"


class Mode(Enum):
    INTERACTIVE = "interactive"
    UNATTENDED = "unattended"


Finding = tuple[Decision, str]


def git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=GIT_TIMEOUT,
    )


def resolve_dir(raw: str, cwd: str) -> str:
    path = expand(raw) or raw
    return os.path.normpath(os.path.join(cwd, path))


def split_git(args: Words, cwd: str) -> tuple[str, str, list[str]]:
    """(repo dir, subcommand, subcommand args) with git's global options consumed."""
    repo = cwd
    texts = [text for _, text in args]
    i = 0
    while i < len(texts) and texts[i].startswith("-"):
        option = texts[i]
        if option in GIT_VALUE_OPTIONS and i + 1 < len(texts):
            if option == "-C":
                repo = resolve_dir(texts[i + 1], repo)
            i += 2
            continue
        i += 1
    if i >= len(texts):
        return repo, "", []
    return repo, texts[i], texts[i + 1 :]


def short_flags(arg: str) -> str:
    return arg[1:] if arg.startswith("-") and not arg.startswith("--") else ""


def force_deleted_branches(args: list[str]) -> list[str]:
    """Branches `git branch <args>` force-deletes; empty when it is not a forced local delete."""
    delete = force = remote = False
    names: list[str] = []
    for arg in args:
        flags = short_flags(arg)
        delete |= arg == "--delete" or "d" in flags or "D" in flags
        force |= arg == "--force" or "D" in flags or "f" in flags
        remote |= arg == "--remotes" or "r" in flags
        if not arg.startswith("-"):
            names.append(arg)
    return names if delete and force and not remote else []


def branch_finding(repo: str, branch: str) -> Finding | None:
    ref = f"refs/heads/{branch}"
    try:
        exists = git(repo, "rev-parse", "--verify", "--quiet", ref).returncode
        if exists == MISSING_REF:
            return None  # git itself reports a missing branch
        unpushed = git(repo, "rev-list", "--count", ref, "--not", "--remotes")
        if exists != 0 or unpushed.returncode != 0:
            return Decision.ASK, f"could not read the state of branch `{branch}` in {repo}"
        if unpushed.stdout.strip() == "0":
            return None
        upstream = git(repo, "rev-parse", "--verify", "--quiet", f"{ref}@{{upstream}}")
        same_name = git(repo, "for-each-ref", "--format=%(refname)", f"refs/remotes/*/{branch}")
    except (OSError, subprocess.SubprocessError):
        return Decision.ASK, f"could not read the state of branch `{branch}` in {repo}"
    if upstream.returncode != 0 and not same_name.stdout.strip():
        return None  # local-only: the user deletes these freely
    count = unpushed.stdout.strip()
    return Decision.ASK, f"branch `{branch}` is on a remote but has {count} commit(s) on no remote"


def push_findings(args: list[str]) -> list[Finding]:
    found: list[Finding] = []
    positional = [arg for arg in args if not arg.startswith("-")]
    if any(arg == "--delete" or "d" in short_flags(arg) for arg in args):
        found.append((Decision.ASK, "`git push --delete` deletes a remote branch"))
    for refspec in positional[1:]:
        if refspec.startswith("+"):
            found.append((Decision.DENY, f"`+{refspec[1:]}` is a force push"))
        elif refspec.startswith(":"):
            found.append((Decision.ASK, f"`{refspec}` deletes a remote branch"))
    return found


def git_findings(args: Words, cwd: str) -> list[Finding]:
    repo, sub, rest = split_git(args, cwd)
    if sub == "push":
        return push_findings(rest)
    if sub != "branch":
        return []
    found: list[Finding] = []
    for branch in force_deleted_branches(rest):
        finding = branch_finding(repo, branch)
        if finding:
            found.append(finding)
    return found


def subcommands(command: str, cwd: str) -> list[tuple[str, Words, str]]:
    """(verb, args, cwd at that point) for each command, following `cd` and nested shells."""
    found: list[tuple[str, Words, str]] = []
    for pipeline in pipelines(command):
        for stage in pipeline:
            for words in stage:
                verb, args, nested, _ = unwrap(words, False)
                if nested is not None:
                    found.extend(subcommands(nested, cwd))
                    continue
                if verb in CD_VERBS:
                    targets = [text for quoted, text in args if quoted or not (text.startswith("-") or text.lower() == "/d")]
                    cwd = resolve_dir(targets[0], cwd) if targets else str(Path.home())
                    continue
                if verb:
                    found.append((verb, args, cwd))
    return found


def settings_paths(cwd: str) -> list[Path]:
    project = Path(cwd) / ".claude"
    return [Path.home() / ".claude" / "settings.json", project / "settings.json", project / "settings.local.json"]


def ask_patterns(cwd: str) -> list[re.Pattern[str]]:
    """Live `permissions.ask` shell rules as regexes over a command's text."""
    patterns: list[re.Pattern[str]] = []
    for path in settings_paths(cwd):
        try:
            rules = json.loads(path.read_text(encoding="utf-8")).get("permissions", {}).get("ask", [])
        except (OSError, ValueError, AttributeError):
            continue
        for rule in rules if isinstance(rules, list) else []:
            match = RULE.match(rule) if isinstance(rule, str) else None
            if not match:
                continue
            body = match.group(2).removesuffix(":*") + (" *" if match.group(2).endswith(":*") else "")
            regex = ".*".join(re.escape(part) for part in body.split("*"))
            patterns.append(re.compile(rf"^{regex}$", re.I | re.S))
    return patterns


def command_text(verb: str, args: Words, cwd: str) -> str:
    """The command as a rule sees it, with git's global options (`-C dir`) dropped."""
    if verb == "git":
        _, sub, rest = split_git(args, cwd)
        return " ".join(["git", sub, *rest]).strip()
    return " ".join([verb, *(text for _, text in args)])


def findings(command: str, cwd: str, mode: Mode) -> list[Finding]:
    found: list[Finding] = []
    patterns = ask_patterns(cwd) if mode is Mode.UNATTENDED else []
    for verb, args, here in subcommands(command, cwd):
        if verb == "git":
            found.extend(git_findings(args, here))
        text = command_text(verb, args, here)
        if any(pattern.match(text) for pattern in patterns):
            found.append((Decision.ASK, f"`{text}` needs approval under permissions.ask"))
    return found


def decide(found: list[Finding], mode: Mode) -> dict[str, str] | None:
    if not found:
        return None
    reasons = "\n- ".join(reason for _, reason in found[:MAX_REASONS])
    if mode is Mode.UNATTENDED:
        reason = (
            f"Unattended run: this needs the user's approval.\n- {reasons}\n"
            "Do not retry it or rephrase it to get around this check. Skip it, continue "
            "with the rest, and list the exact command under the final report's skipped actions."
        )
        return {"permissionDecision": Decision.DENY.value, "permissionDecisionReason": reason}
    decision = Decision.DENY if any(d is Decision.DENY for d, _ in found) else Decision.ASK
    return {"permissionDecision": decision.value, "permissionDecisionReason": f"- {reasons}"}


def main(argv: list[str]) -> int:
    mode = Mode.UNATTENDED if UNATTENDED_FLAG in argv else Mode.INTERACTIVE
    try:
        payload = json.load(sys.stdin)
        command = payload["tool_input"]["command"]
        cwd = payload.get("cwd") or os.getcwd()
    except (ValueError, KeyError, TypeError, AttributeError):
        return 0
    if not isinstance(command, str) or not isinstance(cwd, str):
        return 0
    if mode is Mode.INTERACTIVE and not GIT_HINT.search(command):
        return 0
    output = decide(findings(command, cwd, mode), mode)
    if output:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **output}}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
