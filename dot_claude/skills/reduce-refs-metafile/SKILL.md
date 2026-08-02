---
name: reduce-refs-metafile
description: Use when a Windows ReFS drive or Dev Drive (DevDrive) has millions of files and high Metafile / metadata RAM usage, or when reclaiming file-count and disk on a dev tree bloated by node_modules, package stores, build caches, virtualenvs, or old idle projects.
---

# Reduce ReFS Metafile RAM by Cutting File Count

## Overview

On ReFS, the in-RAM **Metafile** cache scales with the **number of files and
directories** that exist on the volume — not their size. A dev tree is typically
~70% regenerable cache (node_modules, venvs, build output, Unity `Library`). So
the lever is **collapsing file count**: delete cache that rebuilds on demand, and
zip idle projects into one file each.

Two moves, biggest first:
1. **Purge regenerable cache** in idle projects — self-healing, no source lost.
2. **Archive idle projects** off-drive as verified zips, then delete originals.

Windows / PowerShell / 7-Zip specific. Scripts live in `scripts/` and run in order.

## When to Use

- ReFS/Dev Drive Metafile or `System` RAM is multiple GB and file count is in the millions
- A drive has 1M+ files and you want the count down without losing work
- Cleaning up after many cloned/scaffolded projects accumulated

**Not for:** NTFS metadata tuning by itself, or a drive whose bulk is a few large
files (Metafile pressure comes from *count*, not size).

## Procedure

| Step | Script | Effect |
|---|---|---|
| 1. Profile | `1-profile.ps1 -Root D:\` | counts per top folder + cache classification — find the hot roots |
| 2. Activity | `2-activity.ps1 -Root D:\source` | true last-edit date per project → `activity.csv` |
| 3. Find targets | `3-find-purge-targets.ps1 -PurgeDays 90` | list cache dirs in idle projects → `purge-targets.txt` |
| 4. Purge | `4-purge.ps1` then `-Execute` | delete those dirs (dry-run first) |
| 5. Archive | `5-archive.ps1 -ArchiveDays 180 -ArchiveRoot C:\...\Archive` | zip+verify idle projects off-drive |
| 6. Remove originals | `6-remove-archived.ps1 -Execute` | **irreversible** — delete archived folders |

All scripts share a `-WorkDir` (default `%TEMP%\refs-metafile`) holding the CSVs
and logs. Pass the same one to every step.

## Non-Negotiable Safety Rules

These are the judgment calls that keep it from destroying real work:

- **Never trust folder mtime for "idle".** An install or build bumps it. Rank
  projects by the newest mtime among *source* files with cache dirs pruned
  (step 2). That is the only reliable "last worked on" signal.
- **`Library`/`Temp`/`obj` are generic names.** Only treat them as Unity cache
  when the folder is a real Unity project (sibling `Assets` **and**
  `ProjectSettings`). Otherwise you may delete a source folder named `Library`.
- **Don't auto-delete generic build dir names** (`build`, `out`, `dist`) — a
  project may keep meaningful files there. Only delete unambiguous caches:
  `node_modules`, framework dotdirs (`.next/.nuxt/.output/.svelte-kit/.turbo/.angular/.gradle`),
  Unity `Library/Temp/Logs/obj`.
- **Keep a recent-work window.** Leave projects idle < `PurgeDays` fully intact
  so active work needs no reinstall.
- **Archive off-drive.** Put zips on a *different volume* so even the 1 zip/project
  leaves the target drive (and frees its space).
- **Archives keep `.git`, exclude regenerable dirs.** History is preserved;
  node_modules/venvs are not (they rebuild).
- **Verify before delete, twice.** Step 5 runs `7z t` after zipping; step 6
  re-runs `7z t` immediately before deleting each source. No verify → no delete.
- **Deletion is gated.** Steps 4 and 6 are dry-run until `-Execute`. Get explicit
  human approval before `-Execute` on step 6 (source removal).

## Key Techniques

- **Counting fast:** `robocopy <path> <dummy> /L /E /NFL /NDL` is far faster than
  `Get-ChildItem -Recurse`. Its summary labels are localized — parse by digits,
  not the words "Files:"/"Dirs:" (they may be Japanese, etc.).
- **Deleting huge/deep trees:** robocopy empty-mirror
  (`robocopy <empty> <target> /MIR`) then remove the shell. Handles >260-char
  paths that `rd /s /q` and `Remove-Item` fail on.
- **Git Bash mangles `/L`, `/E`** into `L:/` via MSYS path conversion — run
  robocopy from PowerShell, not Git Bash.

## Common Mistakes

- Ranking by folder mtime → deletes an "old" project that's actually current.
- Blanket-deleting any dir named `Library`/`build` → data loss.
- Archiving onto the same drive → file count barely drops.
- `pnpm store prune` after manually deleting node_modules removes 0 (its
  bookkeeping still thinks packages are referenced). To reclaim the store,
  delete it wholesale — it's pure cache — accepting a re-download on next install.
- Deleting archived originals before re-verifying the zip.

## Real-World Impact

First run on a 2.8M-file Dev Drive: `D:\source` went 1.94M → 0.83M files
(−57%, ~1.1M files) from cache purge alone, no source touched; archiving 62 idle
projects queued another ~192K files for removal. Target: cut the 6 GB Metafile
footprint proportionally.
