from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "workcell_hook.py"


class WorkcellHookTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "root"
        self.env = os.environ.copy()
        self.env["WORKCELL_ROOT"] = str(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def invoke(self, payload: dict) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [os.environ.get("PYTHON", "python"), str(HOOK)],
            input=json.dumps(payload),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            check=False,
        )

    def events(self) -> list[dict]:
        path = self.root / "telemetry" / "events.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def test_session_start_announces_root_and_cli(self) -> None:
        self.env["CLAUDE_PLUGIN_ROOT"] = str(self.base / "plugin")
        result = self.invoke({
            "session_id": "s0",
            "hook_event_name": "SessionStart",
            "source": "startup",
        })
        payload = json.loads(result.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "SessionStart")
        # resolve(): Windows temp dirs surface as 8.3 short names, the hook reports long ones.
        self.assertIn(str(self.root.resolve()), context)
        self.assertIn(str((self.base / "plugin").resolve() / "workcell.py"), context)

    def test_non_session_start_writes_nothing_to_stdout(self) -> None:
        result = self.invoke({
            "session_id": "s0",
            "hook_event_name": "Stop",
            "transcript_path": "/missing",
        })
        self.assertEqual(result.stdout, "")

    def test_direct_command_and_skill_are_indexed_without_prompt_content(self) -> None:
        result = self.invoke({
            "session_id": "s1",
            "transcript_path": "/missing",
            "cwd": "/repo",
            "hook_event_name": "UserPromptExpansion",
            "expansion_type": "slash_command",
            "command_name": "workcell-delegate",
            "command_source": "user",
            "prompt": "/workcell-delegate secret text"
        })
        self.assertEqual(result.returncode, 0)
        self.invoke({
            "session_id": "s1",
            "cwd": "/repo",
            "hook_event_name": "PreToolUse",
            "tool_name": "Skill",
            "tool_input": {"skill": "using-workcell"}
        })
        events = self.events()
        self.assertEqual(events[0]["event"], "command_invoked")
        self.assertEqual(events[0]["command_name"], "workcell-delegate")
        self.assertNotIn("prompt", events[0])
        self.assertEqual(events[1]["event"], "skill_invoked")
        self.assertEqual(events[1]["skill"], "using-workcell")

    def test_subagent_transcript_is_archived(self) -> None:
        main = self.base / "main.jsonl"
        agent = self.base / "agent.jsonl"
        main.write_text('{"m":1}\n', encoding="utf-8")
        agent.write_text('{"a":1}\n', encoding="utf-8")
        result = self.invoke({
            "session_id": "s2",
            "transcript_path": str(main),
            "cwd": "/repo",
            "hook_event_name": "SubagentStop",
            "agent_id": "agent-123",
            "agent_type": "team-executor",
            "agent_transcript_path": str(agent),
            "stop_hook_active": False
        })
        self.assertEqual(result.returncode, 0)
        archived = self.root / "telemetry" / "transcripts" / "s2" / "subagents" / "agent-123.jsonl"
        self.assertEqual(archived.read_text(encoding="utf-8"), '{"a":1}\n')
        event = self.events()[0]
        self.assertEqual(event["event"], "subagent_stopped")
        self.assertTrue(event["workcell_agent"])

    def test_main_transcript_sync_is_incremental_and_idempotent(self) -> None:
        main = self.base / "main.jsonl"
        main.write_text('one\n', encoding="utf-8")
        payload = {
            "session_id": "s3",
            "transcript_path": str(main),
            "cwd": "/repo",
            "hook_event_name": "Stop"
        }
        self.invoke(payload)
        archive = self.root / "telemetry" / "transcripts" / "s3" / "main.jsonl"
        self.assertEqual(archive.read_text(encoding="utf-8"), "one\n")
        main.write_text('one\ntwo\n', encoding="utf-8")
        self.invoke(payload)
        self.assertEqual(archive.read_text(encoding="utf-8"), "one\ntwo\n")
        self.invoke(payload)
        self.assertEqual(archive.read_text(encoding="utf-8"), "one\ntwo\n")

    def test_hook_fails_open_on_invalid_json(self) -> None:
        result = subprocess.run(
            [os.environ.get("PYTHON", "python"), str(HOOK)],
            input="not json",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.env,
            check=False,
        )
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
