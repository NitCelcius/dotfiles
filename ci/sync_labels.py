# Applies .github/labels.yml to the GitHub repo: renames `from` labels, then creates or updates the rest.
# Usage: uv run --with pyyaml python ci/sync_labels.py [--apply]   (default is a dry run)
# Input: .github/labels.yml. Output: the gh commands it ran or would run; never deletes labels.
import subprocess
import sys
from pathlib import Path

import yaml

LABELS_FILE = Path(__file__).resolve().parent.parent / ".github" / "labels.yml"


def gh(args: list[str], apply: bool) -> str:
    print("gh", *args)
    if not apply:
        return ""
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def main() -> None:
    apply = "--apply" in sys.argv
    labels = yaml.safe_load(LABELS_FILE.read_text(encoding="utf-8"))
    existing = {row.split("\t")[0] for row in gh(["label", "list", "--limit", "200"], True).splitlines()}

    for label in labels:
        old_name = label.get("from")
        if old_name in existing and label["name"] not in existing:
            gh(["label", "edit", old_name, "--name", label["name"]], apply)
            existing.discard(old_name)
            existing.add(label["name"])

    for label in labels:
        gh(
            ["label", "create", label["name"], "--color", label["color"],
             "--description", label["description"], "--force"],
            apply,
        )

    declared = {label["name"] for label in labels}
    for name in sorted(existing - declared):
        print(f"not in labels.yml, left alone: {name}")


if __name__ == "__main__":
    main()
