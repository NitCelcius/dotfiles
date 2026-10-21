#!/usr/bin/env python3
"""Deny a Bash command that feeds a heredoc into an interpreter's stdin.

Wired as a PreToolUse hook (matcher `Bash`). Reads the hook payload on stdin for
`tool_input.command`. In this Git Bash, `python - <<'EOF'` and the like intermittently
hang until the tool times out, so the command is denied with a pointer to the
write-a-file route. Heredocs that write a file (`cat > f <<'EOF'`) hung rarely enough to
stay allowed.

Matching rule, deliberately not a shell parser: strip quoted strings line by line, find
each `<<` / `<<-` heredoc operator (not `<<<`), take the text before it back to the last
`;`, `|`, `&&`, `||` or newline, and deny when that text names `python`, `python3`,
`python3.12` or `py` as a whole word. Only Python was observed to hang, so other
interpreters stay allowed. `uv run python -I -` and `2>/dev/null` before the `<<` are
covered by the same rule.

Known gaps: an interpreter named inside a heredoc body that itself holds a `<<` line is
denied; an interpreter reached through a wrapper script, `bash -c "..."` or a multi-line
quoted string is not seen.

Unparseable input prints nothing and exits 0: the guard never blocks on its own failure.
"""

from __future__ import annotations

import json
import re
import sys

INTERPRETERS = r"(?:python[\d.]*|py)(?:\.exe)?"

QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'')
HEREDOC = re.compile(r"(?<!<)<<(?!<)")  # `<<<` is a here-string, not a heredoc
STATEMENT_SPLIT = re.compile(r";|&&|\|\||\|")
INTERPRETER_WORD = re.compile(rf"(?<![\w./\\-]){INTERPRETERS}(?=\s|$)", re.I)

REASON = (
    "A heredoc piped into an interpreter's stdin (`python - <<'EOF'`) intermittently hangs in "
    "this Git Bash until the tool times out. Write the script to a file with the Write tool "
    "(scratchpad) and run `uv run python <file>` instead."
)


def feeds_interpreter(command: str) -> bool:
    for line in command.splitlines():
        bare = QUOTED.sub("", line)
        for heredoc in HEREDOC.finditer(bare):
            segment = STATEMENT_SPLIT.split(bare[: heredoc.start()])[-1]
            if INTERPRETER_WORD.search(segment):
                return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload["tool_input"]["command"]
    except (ValueError, KeyError, TypeError, AttributeError):
        return 0
    if not isinstance(command, str) or not feeds_interpreter(command):
        return 0
    output = {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": REASON}
    print(json.dumps({"hookSpecificOutput": output}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
