#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

TASK_PREFIX = "executor-"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def fail(message: str, code: int = 2) -> "NoReturn":
    print(f"workcell: {message}", file=sys.stderr)
    raise SystemExit(code)


def run_git(*args: str, cwd: Path | None = None, required: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        if required:
            fail(proc.stderr.strip() or f"git {' '.join(args)} failed")
        return ""
    return proc.stdout.strip()


def repo_root() -> Path:
    return Path(run_git("rev-parse", "--show-toplevel")).resolve()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today_local() -> str:
    return datetime.now().astimezone().date().isoformat()


def workcell_root() -> Path:
    value = os.environ.get("WORKCELL_ROOT")
    return Path(value).expanduser().resolve() if value else (Path.home() / ".local" / "share" / "workcell").resolve()


def normalize_remote(remote: str) -> str:
    remote = remote.strip()
    if not remote:
        return remote

    # SCP-style SSH URL: git@github.com:owner/repo.git
    scp = re.match(r"^(?:[^@]+@)?([^:]+):(.+)$", remote)
    if scp and "://" not in remote and not re.match(r"^[A-Za-z]:[\\/]", remote):
        host, path = scp.groups()
        normalized = f"{host.lower()}/{path.lstrip('/')}"
    elif "://" in remote:
        parsed = urlparse(remote)
        host = (parsed.hostname or "").lower()
        path = parsed.path.lstrip("/")
        normalized = f"{host}/{path}" if host else remote
    else:
        normalized = str(Path(remote).expanduser().resolve())

    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized.rstrip("/")


def project_identity(root: Path) -> tuple[str, str]:
    remote = run_git("remote", "get-url", "origin", cwd=root, required=False)
    identity = normalize_remote(remote) if remote else str(root.resolve())

    if remote:
        repo_name = identity.rstrip("/").split("/")[-1]
    else:
        repo_name = root.name
    repo_name = re.sub(r"[^A-Za-z0-9._-]+", "-", repo_name).strip("-._") or "repo"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]
    return f"{repo_name}-{digest}", identity


def validate_slug(slug: str) -> str:
    slug = slug.strip().lower()
    if not SLUG_RE.fullmatch(slug):
        fail("slug must match [a-z0-9][a-z0-9-]*")
    return slug


TEMPLATE_SUBPATH = Path("skills") / "using-workcell" / "templates"


def template_dir() -> Path:
    candidates: list[Path] = []
    if os.environ.get("WORKCELL_TEMPLATE_DIR"):
        candidates.append(Path(os.environ["WORKCELL_TEMPLATE_DIR"]).expanduser())
    if os.environ.get("CLAUDE_PLUGIN_ROOT"):
        candidates.append(Path(os.environ["CLAUDE_PLUGIN_ROOT"]) / TEMPLATE_SUBPATH)
    script = Path(__file__).resolve()
    candidates.append(script.parent / TEMPLATE_SUBPATH)

    for candidate in candidates:
        if (candidate / "TASK.md").is_file() and (candidate / "RUN.md").is_file():
            return candidate.resolve()
    fail("cannot locate using-workcell templates; set WORKCELL_TEMPLATE_DIR")


def render_template(name: str, values: dict[str, str]) -> str:
    text = (template_dir() / name).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    leftovers = sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", text)))
    if leftovers:
        fail(f"unresolved template fields in {name}: {', '.join(leftovers)}")
    return text


def parse_frontmatter(text: str) -> tuple[dict[str, str], tuple[int, int]]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        fail("missing YAML frontmatter")
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data, match.span(1)


def update_frontmatter_fields(text: str, updates: dict[str, str]) -> str:
    match = FRONTMATTER_RE.match(text)
    if not match:
        fail("missing YAML frontmatter")
    lines = match.group(1).splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        if ":" in line and not line.lstrip().startswith("#"):
            key = line.split(":", 1)[0].strip()
            if key in updates:
                out.append(f"{key}: {updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    missing = [key for key in updates if key not in seen]
    if missing:
        fail(f"frontmatter missing fields: {', '.join(missing)}")
    replacement = "\n".join(out)
    return text[: match.start(1)] + replacement + text[match.end(1) :]


def require_task_dir(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir() or not (path / "TASK.md").is_file():
        fail(f"not a Workcell task directory: {path}")
    return path


def command_task_create(slug_raw: str) -> None:
    slug = validate_slug(slug_raw)
    root = repo_root()
    project_id, _identity = project_identity(root)
    task_name = TASK_PREFIX + slug
    task_dir = workcell_root() / "projects" / project_id / today_local() / "executors" / task_name
    if task_dir.exists():
        fail(f"task already exists: {task_dir}")

    (task_dir / "history").mkdir(parents=True)
    (task_dir / "runs").mkdir()
    (task_dir / "artifacts").mkdir()

    created = now_iso()
    task_text = render_template(
        "TASK.md",
        {
            "TASK": task_name,
            "REVISION": "1",
            "CREATED_AT": created,
            "UPDATED_AT": created,
        },
    )
    (task_dir / "TASK.md").write_text(task_text, encoding="utf-8", newline="\n")
    print(task_dir)


def command_task_revise(task_dir_raw: str) -> None:
    task_dir = require_task_dir(task_dir_raw)
    task_file = task_dir / "TASK.md"
    original = task_file.read_text(encoding="utf-8")
    meta, _span = parse_frontmatter(original)
    try:
        revision = int(meta["revision"])
    except (KeyError, ValueError):
        fail("TASK revision is missing or invalid")

    history = task_dir / "history" / f"task-rev-{revision:03d}.md"
    if history.exists():
        fail(f"history revision already exists: {history}")
    history.parent.mkdir(parents=True, exist_ok=True)
    history.write_text(original, encoding="utf-8", newline="\n")

    revised = update_frontmatter_fields(
        original,
        {
            "revision": str(revision + 1),
            "status": "preparing",
            "updated_at": now_iso(),
        },
    )
    task_file.write_text(revised, encoding="utf-8", newline="\n")
    print(task_file)


def next_run_number(runs_dir: Path) -> int:
    numbers: list[int] = []
    if runs_dir.exists():
        for child in runs_dir.iterdir():
            match = re.fullmatch(r"run-(\d{3})\.md", child.name)
            if match:
                numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def command_run_create(task_dir_raw: str) -> None:
    task_dir = require_task_dir(task_dir_raw)
    task_text = (task_dir / "TASK.md").read_text(encoding="utf-8")
    meta, _span = parse_frontmatter(task_text)
    task_name = meta.get("task")
    revision = meta.get("revision")
    if not task_name or not revision:
        fail("TASK frontmatter must contain task and revision")

    # The command must be invoked from the main checkout whose HEAD becomes the run base.
    root = repo_root()
    base_commit = run_git("rev-parse", "HEAD", cwd=root)

    runs_dir = task_dir / "runs"
    run_num = next_run_number(runs_dir)
    run_file = runs_dir / f"run-{run_num:03d}.md"
    artifact_dir = task_dir / "artifacts" / f"run-{run_num:03d}"
    if run_file.exists() or artifact_dir.exists():
        fail(f"run {run_num:03d} already exists")

    runs_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True)
    created = now_iso()
    run_text = render_template(
        "RUN.md",
        {
            "TASK": task_name,
            "TASK_REVISION": revision,
            "RUN": str(run_num),
            "CREATED_AT": created,
            "BASE_COMMIT": base_commit,
        },
    )
    run_file.write_text(run_text, encoding="utf-8", newline="\n")
    print(run_file.resolve())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="workcell", description="Workcell template generator")
    sub = parser.add_subparsers(dest="group", required=True)

    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_create = task_sub.add_parser("create")
    task_create.add_argument("slug")
    task_revise = task_sub.add_parser("revise")
    task_revise.add_argument("task_dir")

    run = sub.add_parser("run")
    run_sub = run.add_subparsers(dest="run_command", required=True)
    run_create = run_sub.add_parser("create")
    run_create.add_argument("task_dir")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.group == "task" and args.task_command == "create":
        command_task_create(args.slug)
    elif args.group == "task" and args.task_command == "revise":
        command_task_revise(args.task_dir)
    elif args.group == "run" and args.run_command == "create":
        command_run_create(args.task_dir)
    else:
        fail("unsupported command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
