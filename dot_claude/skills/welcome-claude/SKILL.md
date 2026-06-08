---
name: welcome-claude
description: One-time project onboarding — generates or updates CLAUDE.md with commands, architecture, and language-specific conventions. Run once when starting work in a new repository.
---

# Welcome Claude

Run this once when starting work in a new repository. It produces a CLAUDE.md that future Claude instances will use to operate effectively in this codebase.

**Announce at start:** "I'm using the welcome-claude skill to set up CLAUDE.md."

## Step 1 — Check for existing CLAUDE.md

- If one exists: read it, note what's already covered, and skip any sections below that are already present. Add only what's missing.
- If absent: create it from scratch using the sections below.

Always prefix the file with:

```
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
```

## Step 2 — Commands and architecture (invoke /init)

Invoke the `init` skill now to generate:
- Common commands (build, lint, test, run single test)
- High-level architecture and code structure

Follow the init skill's output exactly. Do not repeat instructions that are already in the global `~/.claude/CLAUDE.md`.

## Step 3 — Detect the project stack

Run these checks in parallel:

```bash
# Languages present
ls *.py pyproject.toml requirements.txt uv.lock 2>/dev/null
ls *.ts *.tsx tsconfig.json package.json 2>/dev/null
```

Also check `pyproject.toml` or `requirements.txt` for framework dependencies:
- `gradio` → apply Gradio block
- `pytest` → apply pytest block
- `torch` / `tensorflow` / `keras` → apply ML training block
- `git lfs` entries in `.gitattributes` → apply LFS block

## Step 4 — Python tooling: syntax-check hook and formatter gate (only if Python detected)

### A. py_compile syntax-check hook

Invoke the `update-config` skill to add a `PostToolUse` hook to this project's `.claude/settings.json`:
- Matcher: `Edit|Write` on files matching `*.py`
- Command: `uv run python -m py_compile <file>`
- Behavior: **non-blocking** — surface failures as feedback to Claude so it can self-correct on the next turn; do not reject the edit. (`py_compile` is read-only, so automating it carries no risk of file drift.)

Record whether this hook was successfully added — it determines which version of the Python conventions block Step 5 writes.

### B. Formatter detection and pre-commit gate check

Detect which formatter the project uses (check in order, stop at first match):
- `[tool.ruff]` in `pyproject.toml`, or `ruff.toml` / `.ruff.toml` present → ruff
- `[tool.black]` in `pyproject.toml` → black
- `[yapf]` in `setup.cfg` → yapf
- none found → skip the rest of this section

Formatters mutate files, so do **not** wire one into a Claude Code hook — a PostToolUse rewrite would leave Claude holding a stale view of content it just wrote, risking failed or duplicated edits on its next turn.

Instead, check whether a git-level pre-commit gate already enforces formatting:
- `.pre-commit-config.yaml` containing a ruff-format / black hook entry
- `.husky/pre-commit` combined with a `lint-staged` config that runs the formatter
- `lefthook.yml` with a formatter command

- **Gate exists:** do nothing further — it already covers every path to a commit (yours, Claude's, `/draft-pr`'s). Do not add a formatting instruction to CLAUDE.md; it would be redundant.
- **No gate exists:** do not write a soft "run the formatter before committing" instruction into CLAUDE.md either — Claude can't enforce that on commits it didn't make. Instead, surface a one-time suggestion to the user, e.g. "This repo uses `<formatter>` but has no pre-commit gate running it — want one set up?", and leave the decision to them.

---

## Step 5 — Append convention blocks

Add only the blocks that match the detected stack. Do not add blocks for absent languages or frameworks.

---

### Python

```markdown
## Python Conventions

- After logic changes: `uv run pytest` before committing
```

If the `py_compile` hook from Step 4A was **not** successfully added (e.g. user declined, or `update-config` unavailable), also add this line to the block above:

```
- After every Python edit: `uv run python -m py_compile <file>` — catches syntax errors before they compound
```

---

### TypeScript / TSX

```markdown
## TypeScript Conventions

- Prefer generic typed helpers over `as` casts — casts discard narrowing and require rework when types change downstream
```

---

### Gradio

```markdown
## Gradio

- Never launch or poll the Gradio server via tool calls — it blocks output capture and stalls verification
- Build the app fully, then give the user the exact command to run it themselves
- Target Gradio v6; asset and API routes are prefixed with `/gradio_api` — debug 404s there first
```

---

### ML training (PyTorch / TensorFlow)

```markdown
## ML / Training Conventions

- Before changing data-handling logic (channels, labels, aggregation): read the actual source and print shapes/dtypes — state the assumption and wait for confirmation before editing
- Before running any experiment or submission script: diff against the last committed baseline and confirm only the intended parameter differs
- Never rename or restructure a training script mid-experiment; create a new numbered config instead
```

---

### Git LFS

```markdown
## Git LFS

- Large binary files (check `.gitattributes` for tracked patterns) are stored via Git LFS — verify LFS path syntax before committing
- Do not `git add` LFS-tracked files without confirming `git lfs` is initialised in the current clone
```

---

## Step 6 — Write and confirm

Write the completed CLAUDE.md to the repository root. Then output a one-line summary:

> "CLAUDE.md written — sections added: [list the section headings you added]."

Do not summarise the file contents beyond that line.
