---
name: pptx2note
description: Use when asked to extract, dump, pull, or export speaker notes from PowerPoint (.pptx) files into text files — e.g. "extract slide notes from these decks", "get the presenter notes out of this pptx", or when the user runs /pptx2note.
---

# pptx2note

## Overview

Extracts speaker notes from every `.pptx` file in a directory into a matching
`<stem>_notes.txt`, one file per slide deck. Uses `python-pptx` via `uv run
--with`, so no project setup or `uv add` is needed.

## When to Use

- User wants speaker/presenter notes pulled out of one or more `.pptx` files.
- Input is a folder of decks (conference slides, talk archives, etc.).

Not for: reading slide *body* text/content (this only reads the notes pane),
or `.ppt` (legacy binary format — not supported by python-pptx).

## Running It

```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 uv run --with python-pptx python \
  ~/.claude/skills/pptx2note/scripts/extract_notes.py "<absolute directory path>"
```

**Both quirks below matter — dropping either one silently breaks non-ASCII paths on Windows:**

- Always set `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`. Without it, filenames
  containing non-ASCII characters (Japanese, accents, etc.) come out mojibake
  in `Path.glob()` output and the script fails to find/open the real files.
- Pass an **absolute** path, not `.`. On Windows, when invoked from a bash
  shell whose cwd itself contains non-ASCII characters, a relative `.` can
  resolve incorrectly for the Windows-native Python process launched by
  `uv run`. Get it with `pwd -W` (git-bash) and pass it in `C:/Users/...`
  form.

## Output Format

One `.txt` per source deck, written alongside it:

```
--- Slide 1 ---
<notes text>

--- Slide 2 ---
(no notes)
```

Slides with an empty or missing notes pane get `(no notes)` rather than a
blank block, so slide count stays verifiable against the deck.

## Files That Fail

Password-protected/encrypted `.pptx` files are OLE compound files (`file`
reports `CDFV2 Encrypted`), not the zip-based OOXML format python-pptx reads
— they raise `PackageNotFoundError`. The script catches this per-file, prints
`FAILED to open <name>: <error>`, and continues the batch rather than
aborting. Report failed files back to the user; if they unlock/re-save the
file (e.g. via PowerPoint's "Remove Password"), just rerun — already-written
`_notes.txt` files are overwritten cleanly on rerun.

## Common Mistakes

| Mistake | Symptom |
|---|---|
| Omitting `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8` | Non-ASCII filenames garbled or "Package not found" for files that do exist |
| Passing `.` instead of an absolute path | Same as above, on dirs with non-ASCII names |
| Assuming a failed file is corrupt | Check `file <name>.pptx` first — `CDFV2 Encrypted` means password-protected, not broken |
