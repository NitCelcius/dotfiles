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
# Unity project
ls ProjectSettings/ProjectVersion.txt 2>/dev/null
```

Also check `pyproject.toml` or `requirements.txt` for framework dependencies:
- `gradio` → apply Gradio block
- `pytest` → apply pytest block
- `torch` / `tensorflow` / `keras` → apply ML training block
- `git lfs` entries in `.gitattributes` → apply LFS block
- `ProjectSettings/ProjectVersion.txt` present → run Step 4C (Unity-MCP skill install), then apply Unity block

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

## Step 4C — Unity-MCP skill install (only if Unity detected)

The `unity-mcp-*` skills (`unity-mcp-core` + 7 domain skills) are optional and project-local — they live in the dotfiles source but are not chezmoi-applied globally, so a fresh machine or a non-Unity project never carries them. Install them into *this* project only:

1. Confirm `dot_claude/skills/unity-mcp-core` isn't already present at `.claude/skills/unity-mcp-core` in this repo — skip the rest of this step if it is.
2. Resolve the dotfiles source: run `chezmoi source-path`.
   - If chezmoi isn't installed or isn't initialized (command fails), tell the user: "Unity project detected, but I can't find the dotfiles checkout (chezmoi source-path failed) to copy the unity-mcp-* skills from — install them manually or make chezmoi available, then re-run welcome-claude." Skip the rest of this step; still write the Unity block in Step 5 if any of these skills are already present locally.
3. Copy `unity-mcp-core` and all 7 domain skills (`unity-mcp-scene-objects`, `unity-mcp-scripting`, `unity-mcp-assets-materials`, `unity-mcp-ui`, `unity-mcp-camera-graphics`, `unity-mcp-testing-editor`, `unity-mcp-packages-docs`) from `<source-path>/dot_claude/skills/` into this project's `.claude/skills/`.
4. Add each copied skill directory to `.git/info/exclude` (not `.gitignore` — these are local tooling, not project source; see the dotfiles convention). Create `.claude/skills/` and `.git/info/exclude` if they don't exist yet.
5. Note in your summary at the end which skills were installed.

This does **not** apply to `unity-mcp-skill` (the older monolithic one) — that one is vendored and kept in sync by the Unity MCP Unity-package itself, independent of chezmoi and this step. If `.claude/skills/unity-mcp-skill/` already exists (with a `.unity-mcp-skill-sync` marker), leave it alone.

---

## Step 4D — Direct-commit guard on the default branch (any git repo)

The user's convention is that work reaches the default branch through a branch and a PR, not a
direct commit. This is a *convention*, not a policy to impose — GitHub is typically not configured
to enforce it, and the user has explicitly declined `permissions.deny` rules for it. Offer the gate
once and take no for an answer. Never add permission rules or blocking Claude Code hooks for this.

Prefer a git-level pre-commit hook over a Claude Code hook for the same reason as Step 4B: it covers
every path to a commit — the user's, Claude's, and `/draft-pr`'s — not just the ones Claude makes.

1. Skip this step entirely if any of these hold:
   - not a git repo
   - `.githooks/pre-commit` already exists
   - `git config --get core.hooksPath` already resolves to a directory containing a `pre-commit`
   - `.pre-commit-config.yaml`, `.husky/pre-commit`, or `lefthook.yml` already runs a branch check
2. Ask once: *"Want a pre-commit hook that refuses commits made directly on `<default-branch>`?
   It has an `ALLOW_MAIN=1` escape hatch."* If declined, do nothing and don't raise it again.
3. If accepted, resolve the dotfiles checkout with `chezmoi source-path` and copy
   `<source-path>/.githooks/pre-commit` into this repo's `.githooks/`. If chezmoi isn't available,
   say so and skip — don't hand-write a substitute.
4. Wire it up, all three of which are required:
   - `git config core.hooksPath .githooks` — **per-clone local config, not tracked**, so it has to be
     re-run in every clone. Say this out loud; a hook nobody enabled looks identical to one that passes.
   - `git update-index --chmod=+x .githooks/pre-commit` — git on macOS and Linux skips a hook without
     the executable bit and reports nothing. On Windows `core.fileMode` is off, so the bit will not be
     recorded on its own.
   - Add `.githooks/** text eol=lf` to `.gitattributes` if the repo normalizes with `* text=auto`;
     otherwise a Windows checkout rewrites the shebang to `#!/bin/sh` and the hook fails silently.
5. Verify before claiming it works: with the default branch checked out, stage something and run
   `git commit`. Confirm it exits non-zero and the commit does not land. A hook that was never
   enabled produces exactly the same output as a repo with no hook at all.
6. Note in your summary whether the guard was installed, declined, or already present.

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

### Unity

Check `.claude/skills/` in this project (after Step 4C has run) before writing the block:

- `unity-mcp-core/` present → point at it first (editor-state/compile/batch/console basics, needed before any MCP call), then the domain skill matching the task at hand (`unity-mcp-scene-objects`, `unity-mcp-scripting`, `unity-mcp-assets-materials`, `unity-mcp-ui`, `unity-mcp-camera-graphics`, `unity-mcp-testing-editor`, `unity-mcp-packages-docs`).
- Else `unity-mcp-skill/` present (installed independently by the Unity MCP plugin) → point at that instead, and note it's plugin-synced — don't hand-edit it, changes can be silently overwritten on the next plugin sync.
- Neither present (e.g. Step 4C couldn't reach the dotfiles source) → skip the block entirely; don't invent a skill reference that isn't installed.

```markdown
## Unity (MCP)

Unity Editor automation runs through `mcp__UnityMCP__*`, with the Editor open. [Insert whichever skill pointer applies from the check above — name the actual skill(s) installed in this project.]
```

---

## Step 6 — Write and confirm

Write the completed CLAUDE.md to the repository root. Then output a one-line summary:

> "CLAUDE.md written — sections added: [list the section headings you added]."

Do not summarise the file contents beyond that line.
