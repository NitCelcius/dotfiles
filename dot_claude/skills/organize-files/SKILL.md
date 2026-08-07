---
name: organize-files
description: Use when asked to organize, sort, tidy, clean up, or declutter a messy folder (e.g. Downloads, a shared drive, a project dump) into subfolders.
---

# organize-files

Scan a messy folder, classify files by filename pattern, and propose a
move plan for approval. **Never move or delete anything until the user
approves the plan.**

## Steps

1. **Ask for source and destination folders.** Never assume Downloads or
   any other default — folders vary per run. If the destination already
   exists, list its current top-level subfolder names first: reuse those
   names for matching categories instead of inventing new ones (e.g. if
   the destination already has `Lab-Admin/`, file admin docs there, don't
   create `Administrative/`).
2. **List filenames only** (`Get-ChildItem` / `ls`, names + extensions).
   Don't read file contents unless a name is genuinely ambiguous — the
   classification below runs on filenames.
3. **Classify each item** using the patterns below. A file can only match
   one category — check in roughly this order, since some patterns
   overlap (e.g. a poster PDF is both "slides" and could look like
   "reference literature"; filename intent wins over extension).
4. **Directories that already look self-contained** (existing project
   folders, tool installs, dataset dumps) move as a single unit — don't
   recurse into them or re-sort their contents.
5. **Keep every version.** Files with version/revision markers
   (`_v2`, `_re3`, `_bef`, `_fin`, `_rev`, `(1)`, ` 2`) belong grouped
   together under one folder per document — never treat this as
   duplication to clean up. This skill groups; it does not deduplicate
   or delete.
6. **Anything that doesn't clearly match a category goes in a
   `_needs-review` bucket** — don't force a fit.
7. **Output the plan**, not the move: a markdown table or tree of
   `category → destination subfolder → files`, with counts per category.
   Flag anything you're unsure about. Also write the plan as a CSV with
   `Name,Destination` columns (`Name` = item in the source folder,
   `Destination` = path relative to the destination root). Leave
   `Destination` blank (or `_needs-review...`) for anything not approved
   to move — the executor below treats that as "leave in place."
8. **Only after explicit approval**, execute the moves with
   `scripts/execute-move.ps1` (`-SourceDir`, `-DestRoot`, `-PlanCsv`) —
   don't hand-roll a new mover each time. It never overwrites (same-named
   item at the destination is left alone and reported as a collision,
   not clobbered), and it's resilient: a locked/in-use file is caught and
   reported in `failed.csv` instead of aborting the rest of the batch.
   It's also safe to re-run — items already moved are silently skipped.
   Report `collisions.csv` and `failed.csv` back to the user; don't treat
   the run as fully done until those are empty or explicitly acknowledged.

## Classification patterns

| Category | Filename signals | Group by |
|---|---|---|
| Versioned drafts / manuscripts | `_v#`, `_re#`, `_bef`, `_fin`, `_rev#`, `(1)`, repeated base name across many files | strip version tokens → common base name / paper or doc title |
| Structured session logs | `<id>_<session>_<name>_<date>_<type>.ext` repeated across many rows, e.g. `s12_a2_matsubuchi_260520_event_log.json` | the id/name/participant token |
| Survey / form exports | "アンケート", "survey", "response", "フォームの回答", form-tool export naming | the survey/study name |
| Slides & posters | `.pptx`/`.key`, "スライド", "ポスター", "poster", "slide", conference/venue name in filename | venue or presentation name |
| ML / competition artifacts | `submission*.csv`, "leaderboard", `.ipynb`, model/dataset zips, score suffixes like `_t0.91` | competition/task name |
| Certificates & admin | "修了証", "certificate", "receipt", "任用調書", invoices, static one-off admin docs | admin/年度 (year) if relevant, else flat |
| Reference literature | Academic-paper-style names (DOI/journal formatting, author-year), not authored by the user | leave flat or by topic |
| Generated images / screenshots | "ChatGPT Image", "Gemini_Generated_Image", "スクリーンショット", "Screenshot" | flat, by source tool if volume is high |
| Installers & utilities | `.exe`, `.iso`, `.msi`, known portable-tool names | flat "Tools" bucket |
| Self-contained directories | any existing subfolder | move as-is, unit |

These are starting patterns, not a fixed taxonomy — adapt category names
to what's actually present, and always prefer folder names that already
exist at the destination.

## Common mistakes

- Moving files before the user approves the plan.
- Deleting or picking a "best" version among `_re#`/`_v#` files — not this
  skill's job.
- Digging inside an existing project folder to re-sort its contents.
- Inventing new category folder names when a matching one already exists
  at the destination.
- Hand-writing a new `Move-Item` loop instead of using
  `scripts/execute-move.ps1` — a hand-rolled one is easy to make
  non-resilient (one locked file aborts the whole batch) or destructive
  (overwrites on a name collision).
- Hard-typing a Unicode/Japanese filename as a dictionary key/override and
  assuming it matches the file on disk — normalization mismatches can
  make it silently never match. Prefer selecting the item via
  `Get-ChildItem`/its `.Name` property over retyping the literal string.
