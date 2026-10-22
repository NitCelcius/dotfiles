# Checks whether a fresh, headless session records a friction with enough context.
# Usage: uv run python run_context_test.py <out dir>   (needs the friction skill applied to ~/.claude)
# Runs each case with `claude -p` in a throwaway git repo under dontAsk permission mode, so the
# Notion write is attempted but denied. Writes <out>/<case>.jsonl and prints a pass table.
import json
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

DATA_SOURCE_ID = "6943285c-cdf8-4ff4-8a6e-d53934296ee9"
WRITE_TOOLS = ("notion-create-pages", "notion-update-page")
TIMEOUT_S = 300

# (case id, prompt, expected 種別). Explicit /friction calls first, then requests that never name it.
CASES = [
    ("explicit-friction", "/friction ビルドキャッシュがまた壊れて、毎回クリーンビルドが必要になる", "摩擦"),
    ("explicit-idea", "/friction PR 本文のレビューを省略できるモードがほしい", "アイデア"),
    ("explicit-miss", "/friction コミット前に git-workflow スキルが読み込まれなかった", "スキル発火ミス"),
    ("implicit-friction", "ツールの出力が文字化けしてまた手戻りになった。記録しておいて", "摩擦"),
    ("implicit-idea", "忘れないように、テストを一括で実行するアイデアを残しておいて", "アイデア"),
    ("implicit-miss", "さっきの作業で使うべきスキルが発火しなかった。ログに残しておいて", "スキル発火ミス"),
]


def run_case(prompt: str, project: Path, out_file: Path) -> list[dict]:
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--permission-mode", "dontAsk", "--allowedTools", "Bash", "Skill"]
    proc = subprocess.run(cmd, cwd=project, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT_S)
    out_file.write_text(proc.stdout, encoding="utf-8")
    events = []
    for line in proc.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def check(events: list[dict], expected_kind: str, host: str, project_name: str) -> dict:
    session = next((e.get("session_id") for e in events if e.get("type") == "system"), None)
    writes = []
    for e in events:
        for c in (e.get("message") or {}).get("content") or []:
            if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name", "").endswith(WRITE_TOOLS):
                writes.append(c.get("input") or {})
    if not writes:
        return {"attempted": False}
    inp = writes[0]
    pages = inp.get("pages") or [{}]
    props = pages[0].get("properties") or inp.get("properties") or {}
    parent = json.dumps(inp.get("parent") or inp.get("page_id") or "")
    return {
        "attempted": True,
        "database": DATA_SOURCE_ID in parent or "page_id" in inp,
        "kind": props.get("種別") == expected_kind if "pages" in inp else None,
        "host": props.get("端末") == host if "pages" in inp else None,
        "project": props.get("プロジェクト") == project_name if "pages" in inp else None,
        "session": bool(session) and props.get("セッション") == session if "pages" in inp else None,
        "content": bool(str(props.get("内容", "")).strip()) if "pages" in inp else None,
    }


def main():
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname()
    cols = ["attempted", "database", "kind", "host", "project", "session", "content"]
    print("| case | " + " | ".join(cols) + " |")
    print("|---|" + "---|" * len(cols))
    passed = 0
    for case_id, prompt, kind in CASES:
        with tempfile.TemporaryDirectory(prefix="friction-ctx-") as tmp:
            project = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=project, check=True)
            events = run_case(prompt, project, out_dir / f"{case_id}.jsonl")
            result = check(events, kind, host, project.name)
        cells = [{True: "ok", False: "FAIL", None: "-"}[result.get(c)] for c in cols]
        passed += all(result.get(c) is not False for c in cols) and result["attempted"]
        print(f"| {case_id} | " + " | ".join(cells) + " |")
    print(f"\n{passed}/{len(CASES)} cases passed. A case passes when a write was attempted and no check failed.")


if __name__ == "__main__":
    main()
