from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
CLI = PLUGIN_DIR / "workcell.py"
TEMPLATES = PLUGIN_DIR / "skills" / "using-workcell" / "templates"


class WorkcellCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.root = self.base / "workcell-root"
        subprocess.run(["git", "init"], cwd=self.repo, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        # A global commit.gpgsign would make the fixture commit depend on a signing agent.
        subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=self.repo, check=True)
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.repo, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "remote", "add", "origin", "git@github.com:NitCelcius/example.git"], cwd=self.repo, check=True)
        self.env = os.environ.copy()
        self.env["WORKCELL_ROOT"] = str(self.root)
        self.env["WORKCELL_TEMPLATE_DIR"] = str(TEMPLATES)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_cli(self, *args: str, check: bool = True):
        return subprocess.run(
            [os.environ.get("PYTHON", "python"), str(CLI), *args],
            cwd=self.repo,
            env=self.env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def test_task_create_and_duplicate_rejection(self) -> None:
        result = self.run_cli("task", "create", "session-race")
        task_dir = Path(result.stdout.strip())
        self.assertTrue((task_dir / "TASK.md").is_file())
        self.assertTrue((task_dir / "history").is_dir())
        self.assertTrue((task_dir / "runs").is_dir())
        self.assertIn("task: executor-session-race", (task_dir / "TASK.md").read_text(encoding="utf-8"))

        duplicate = self.run_cli("task", "create", "session-race", check=False)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("already exists", duplicate.stderr)

    def test_revise_archives_and_increments_revision(self) -> None:
        task_dir = Path(self.run_cli("task", "create", "revise-me").stdout.strip())
        task_file = task_dir / "TASK.md"
        original = task_file.read_text(encoding="utf-8")
        task_file.write_text(original.replace("# Goal\n", "# Goal\n\nChanged goal text\n"), encoding="utf-8")
        self.run_cli("task", "revise", str(task_dir))

        history = task_dir / "history" / "task-rev-001.md"
        self.assertTrue(history.is_file())
        self.assertIn("Changed goal text", history.read_text(encoding="utf-8"))
        revised = task_file.read_text(encoding="utf-8")
        self.assertIn("revision: 2", revised)
        self.assertIn("status: preparing", revised)
        self.assertIn("Changed goal text", revised)

    def test_run_numbering_and_base_commit(self) -> None:
        task_dir = Path(self.run_cli("task", "create", "run-test").stdout.strip())
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.repo, text=True).strip()
        run1 = Path(self.run_cli("run", "create", str(task_dir)).stdout.strip())
        run2 = Path(self.run_cli("run", "create", str(task_dir)).stdout.strip())
        self.assertEqual(run1.name, "run-001.md")
        self.assertEqual(run2.name, "run-002.md")
        text = run1.read_text(encoding="utf-8")
        self.assertIn(f"base_commit: {head}", text)
        self.assertTrue((task_dir / "artifacts" / "run-001").is_dir())
        self.assertTrue((task_dir / "artifacts" / "run-002").is_dir())

    def test_remote_project_id_is_stable_across_paths(self) -> None:
        first = Path(self.run_cli("task", "create", "first").stdout.strip())
        project_dir = first.parents[2]
        self.assertRegex(project_dir.name, r"^example-[0-9a-f]{8}$")


if __name__ == "__main__":
    unittest.main()
