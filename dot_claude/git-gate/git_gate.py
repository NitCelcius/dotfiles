#!/usr/bin/env python3
"""Gate the git deletes and pushes that static permission rules cannot judge.

Wired as a PreToolUse hook (matcher `Bash|PowerShell`). Reads the hook payload on
stdin for `tool_input.command` and `cwd`, and splits the command with the lexer in
`rm-junction-guard`, tracking `cd`/`Set-Location`/`pushd` and `git -C` to find each repo.

  - `git branch -D` (or `-d` with `-f`, in any spelling git accepts) asks for a branch
    that has commits on no remote-tracking ref and still has a remote counterpart (an
    upstream or a same-name remote branch). A local-only branch, or one whose commits
    are all pushed, is cleared.
  - A forced delete also asks when its repo cannot be pinned down: `GIT_DIR` or
    `GIT_WORK_TREE` set, `--git-dir`/`--work-tree`, `env -C`, `popd`, or a `cd` inside
    parentheses or to an unexpanded variable.
  - A `git worktree remove` without `--force` is cleared: git refuses it while the
    worktree has changes or untracked files. Gitignored files in it still go, like any
    other delete the hook does not judge.
  - When every command in the call is cleared or only changes directory, the hook
    returns `allow`. Otherwise a cleared delete stays silent and the permission rules
    decide; no static rule allows `git branch -D`, so a hook that fails or times out
    leaves the delete to a prompt.
  - `git push` with a `+refspec` or `--force` is denied; with a `:refspec`, `--delete`,
    `--mirror`, `--prune` or `--force-with-lease`, in any argument order, it asks.

With `--unattended` (registered by the `unattended-run` skill) every one of those asks,
and every command a live `permissions.ask` rule matches, is denied with a reason
instead, so an unattended run skips the action and keeps going rather than waiting on
a prompt.

Outside `--unattended`, a command with no `git` exits at once with no output.
Unparseable input prints nothing; a branch whose state cannot be read asks.
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
from rm_junction_guard import TOKEN, expand, pipelines, stage_commands, verb_of  # noqa: E402

UNATTENDED_FLAG = "--unattended"
GIT_HINT = re.compile(r"(?<![\w-])git(?![\w-])", re.I)
MISSING_REF = 1  # `git rev-parse --verify --quiet` exit code for a ref that does not exist
CD_VERBS = frozenset({"cd", "set-location", "sl", "chdir", "pushd", "push-location"})
CD_RESETS = frozenset({"popd", "pop-location"})  # back to a directory the hook did not track
GIT_VALUE_OPTIONS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"})
REPO_OPTIONS = frozenset({"--git-dir", "--work-tree"})
REPO_ENV = re.compile(r"^(?:\$env:)?GIT_(?:DIR|WORK_TREE)(?:=|$)", re.I)
ENV_CHDIR = frozenset({"-C", "--chdir"})
PUSH_VALUE_OPTIONS = frozenset({"-o", "--push-option", "--repo", "--receive-pack", "--exec"})
# git takes any unambiguous prefix of a long option (`--del --forc`); the shortest one
# counted here may be ambiguous, which git rejects, so counting it only asks more.
LONG_OPTION_MIN = {"--delete": 4, "--force": 4, "--remotes": 5, "--mirror": 4, "--prune": 5}
RULE = re.compile(r"^(Bash|PowerShell)\((.*)\)$", re.S)
GIT_TIMEOUT_SEC = 5
MAX_REASONS = 10

Words = list[tuple[bool, str]]


class Decision(Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class Mode(Enum):
    INTERACTIVE = "interactive"
    UNATTENDED = "unattended"


class Verdict(Enum):
    CLEARED = "cleared"  # checked here and safe
    MOVES = "moves"  # only changes directory
    OTHER = "other"  # not judged here; the permission rules decide


Finding = tuple[Decision, str]


def git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=GIT_TIMEOUT_SEC,
    )


def resolve_dir(raw: str, cwd: str | None) -> str | None:
    path = expand(raw)
    if path is None or cwd is None:
        return None
    return os.path.normpath(os.path.join(cwd, path))


def is_option(arg: str, option: str) -> bool:
    return len(arg) >= LONG_OPTION_MIN[option] and option.startswith(arg)


def short_flags(arg: str) -> str:
    return arg[1:] if arg.startswith("-") and not arg.startswith("--") else ""


def split_git(args: Words, cwd: str | None) -> tuple[str | None, str, list[str]]:
    """(repo dir, subcommand, subcommand args) with git's global options consumed; the
    repo is None when an option points git somewhere the hook does not resolve."""
    repo = cwd
    texts = [text for _, text in args]
    i = 0
    while i < len(texts) and texts[i].startswith("-"):
        option, _, value = texts[i].partition("=")
        if option in REPO_OPTIONS:
            repo = None
        if option in GIT_VALUE_OPTIONS and not value and i + 1 < len(texts):
            if option == "-C":
                repo = resolve_dir(texts[i + 1], repo)
            i += 2
            continue
        i += 1
    if i >= len(texts):
        return repo, "", []
    return repo, texts[i], texts[i + 1 :]


def get_force_deleted_branches(args: list[str]) -> list[str]:
    """Branches `git branch <args>` force-deletes; empty when it is not a forced local delete."""
    delete = force = remote = False
    names: list[str] = []
    for arg in args:
        flags = short_flags(arg)
        delete |= is_option(arg, "--delete") or "d" in flags or "D" in flags
        force |= is_option(arg, "--force") or "D" in flags or "f" in flags
        remote |= is_option(arg, "--remotes") or "r" in flags
        if not arg.startswith("-"):
            names.append(arg)
    return names if delete and force and not remote else []


def branch_finding(repo: str, branch: str) -> tuple[bool, Finding | None]:
    """(cleared, finding) for force-deleting `branch` in `repo`."""
    ref = f"refs/heads/{branch}"
    unreadable = Decision.ASK, f"could not read the state of branch `{branch}` in {repo}"
    try:
        exists = git(repo, "rev-parse", "--verify", "--quiet", ref).returncode
        if exists == MISSING_REF:
            return False, None  # git itself reports a missing branch
        unpushed = git(repo, "rev-list", "--count", ref, "--not", "--remotes")
        if exists != 0 or unpushed.returncode != 0:
            return False, unreadable
        if unpushed.stdout.strip() == "0":
            return True, None
        upstream = git(repo, "rev-parse", "--verify", "--quiet", f"{ref}@{{upstream}}")
        same_name = git(repo, "for-each-ref", "--format=%(refname)", f"refs/remotes/*/{branch}")
    except (OSError, subprocess.SubprocessError):
        return False, unreadable
    if upstream.returncode != 0 and not same_name.stdout.strip():
        return True, None  # local-only: the user deletes these freely
    count = unpushed.stdout.strip()
    return False, (Decision.ASK, f"branch `{branch}` is on a remote but has {count} commit(s) on no remote")


def push_findings(args: list[str]) -> list[Finding]:
    found: list[Finding] = []
    positional: list[str] = []
    takes_value = False
    for arg in args:
        if takes_value:
            takes_value = False
            continue
        takes_value = arg in PUSH_VALUE_OPTIONS
        if not arg.startswith("-"):
            positional.append(arg)
    if any(is_option(arg, "--force") or "f" in short_flags(arg) for arg in args):
        found.append((Decision.DENY, "`git push --force` is a force push"))
    if any(arg.startswith("--force-") for arg in args):
        found.append((Decision.ASK, "`git push --force-with-lease` rewrites remote history"))
    if any(is_option(arg, "--delete") or "d" in short_flags(arg) for arg in args):
        found.append((Decision.ASK, "`git push --delete` deletes a remote branch"))
    if any(is_option(arg, "--mirror") for arg in args):
        found.append((Decision.ASK, "`git push --mirror` force-updates and deletes remote branches"))
    if any(is_option(arg, "--prune") for arg in args):
        found.append((Decision.ASK, "`git push --prune` deletes remote branches with no local counterpart"))
    for refspec in positional[1:]:
        if refspec.startswith("+"):
            found.append((Decision.DENY, f"`+{refspec[1:]}` is a force push"))
        elif refspec.startswith(":"):
            found.append((Decision.ASK, f"`{refspec}` deletes a remote branch"))
    return found


def is_plain_worktree_remove(args: list[str]) -> bool:
    if not args or args[0] != "remove":
        return False
    return not any(is_option(arg, "--force") or "f" in short_flags(arg) for arg in args[1:])


def judge_git(args: Words, cwd: str | None) -> tuple[Verdict, list[Finding]]:
    repo, sub, rest = split_git(args, cwd)
    if sub == "push":
        return Verdict.OTHER, push_findings(rest)
    if sub == "worktree":
        return (Verdict.CLEARED if is_plain_worktree_remove(rest) else Verdict.OTHER), []
    branches = get_force_deleted_branches(rest) if sub == "branch" else []
    if not branches:
        return Verdict.OTHER, []
    if repo is None:
        return Verdict.OTHER, [(Decision.ASK, "could not tell which repo the forced `git branch` delete runs in")]
    found: list[Finding] = []
    cleared = True
    for branch in branches:
        safe, finding = branch_finding(repo, branch)
        cleared &= safe
        if finding:
            found.append(finding)
    return (Verdict.CLEARED if cleared else Verdict.OTHER), found


def points_git_elsewhere(command: str) -> bool:
    """Whether the command sets GIT_DIR/GIT_WORK_TREE or runs `env -C`."""
    bare = [word for _, _, _, word in TOKEN.findall(command)]
    for i, word in enumerate(bare):
        if REPO_ENV.match(word):
            return True
        if verb_of(word) != "env":
            continue
        for option in bare[i + 1 :]:
            if not option.startswith("-") and "=" not in option:
                break
            if option in ENV_CHDIR or option.startswith("--chdir="):
                return True
    return False


def subcommands(command: str, cwd: str | None) -> list[tuple[str, Words, str | None]]:
    """(verb, args, cwd at that point) for each command, following `cd` and nested shells.

    The cwd turns None once the hook cannot tell where later commands run.
    """
    if points_git_elsewhere(command):
        cwd = None
    in_subshell = any(op in ("(", ")") for _, _, op, _ in TOKEN.findall(command))
    found: list[tuple[str, Words, str | None]] = []
    for pipeline in pipelines(command):
        for _, verb, args, nested, _ in stage_commands(pipeline, under_cmd=False):
            if nested is not None:
                found.extend(subcommands(nested, cwd))
                continue
            if not verb:
                continue
            found.append((verb, args, cwd))
            if verb in CD_RESETS or (verb in CD_VERBS and in_subshell):
                cwd = None
            elif verb in CD_VERBS:
                targets = [text for quoted, text in args if quoted or not (text.startswith("-") or text.lower() == "/d")]
                cwd = resolve_dir(targets[0], cwd) if targets else str(Path.home())
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


def command_text(verb: str, args: Words, cwd: str | None) -> str:
    """The command as a rule sees it, with git's global options (`-C dir`) dropped."""
    if verb == "git":
        _, sub, rest = split_git(args, cwd)
        return " ".join(["git", sub, *rest]).strip()
    return " ".join([verb, *(text for _, text in args)])


def findings(command: str, cwd: str, mode: Mode) -> tuple[list[Finding], bool]:
    """Findings, and whether the call is all cleared or directory changes, with at least one cleared."""
    found: list[Finding] = []
    patterns = ask_patterns(cwd) if mode is Mode.UNATTENDED else []
    all_cleared, any_cleared = True, False
    for verb, args, here in subcommands(command, cwd):
        verdict = Verdict.MOVES if verb in CD_VERBS | CD_RESETS else Verdict.OTHER
        if verb == "git":
            verdict, git_found = judge_git(args, here)
            found.extend(git_found)
        text = command_text(verb, args, here)
        if any(pattern.match(text) for pattern in patterns):
            found.append((Decision.ASK, f"`{text}` needs approval under permissions.ask"))
        all_cleared &= verdict is not Verdict.OTHER
        any_cleared |= verdict is Verdict.CLEARED
    return found, all_cleared and any_cleared


def decide(found: list[Finding], cleared: bool, mode: Mode) -> dict[str, str] | None:
    if not found:
        if not cleared:
            return None
        reason = "git-gate checked it: no forced delete here drops unpushed commits of a remote-backed branch"
        return {"permissionDecision": Decision.ALLOW.value, "permissionDecisionReason": reason}
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
    output = decide(*findings(command, cwd, mode), mode)
    if output:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **output}}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
