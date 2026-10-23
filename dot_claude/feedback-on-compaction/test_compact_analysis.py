"""Check which repeated reads compact_analysis attributes to a compaction.

Run: uv run --with pytest pytest dot_claude/feedback-on-compaction

A repeat counts as a re-read only when its target was first read before an earlier
compaction; a repeat between the same two compactions does not.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compact_analysis

STEP_TOKENS = 200
RESULT_CHARS = 400


def assistant(request_id: str, context: int, tool_id: str | None, file_path: str | None) -> dict:
    content = [{"type": "tool_use", "id": tool_id, "name": "Read", "input": {"file_path": file_path}}] if tool_id else []
    return {
        "type": "assistant",
        "requestId": request_id,
        "timestamp": f"2026-01-01T00:00:{len(request_id):02d}Z",
        "message": {
            "id": request_id,
            "model": "claude-opus-5",
            "stop_reason": "tool_use" if tool_id else "end_turn",
            "usage": {"input_tokens": context, "output_tokens": 0},
            "content": content,
        },
    }


def result(tool_id: str) -> dict:
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id, "content": "x" * RESULT_CHARS}]}}


def write_transcript(path: Path) -> None:
    # A and B are read before the compaction; after it, A is read again (with a
    # different range) and C is read twice.
    reads = [("a", "A"), ("b", "B"), None, ("a2", "A"), ("c", "C"), ("c2", "C"), ("end", None)]
    rows: list[dict] = []
    context = 1000
    for step, read in enumerate(reads):
        if read is None:
            rows.append({"type": "system", "subtype": "compact_boundary", "compactMetadata": {}})
            continue
        tool_id, file_path = read
        rows.append(assistant(f"req{step:02d}", context, f"tool-{tool_id}" if file_path else None, file_path))
        if file_path:
            rows.append(result(f"tool-{tool_id}"))
        context += STEP_TOKENS
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_only_reads_from_before_the_compaction_count(tmp_path: Path) -> None:
    transcript = tmp_path / "session.jsonl"
    write_transcript(transcript)

    requests, _ = compact_analysis.parse_claude_file(transcript)

    # Only the request after A's second read carries re-read tokens; C's repeat does not.
    assert [r.reread_tokens_est for r in requests] == [0, 0, 0, STEP_TOKENS, 0, 0]
