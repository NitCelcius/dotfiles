---
name: organize-photos
description: Sorts a photo or media folder by date and archives it into password-protected 7z files. Use when asked to organize photos.
---

# Organize Photos by Date, Then Archive

## Overview

Two PowerShell scripts, run in order, that live in the
`Powershell_date_to_folder` repo (canonical source —
`D:\source\Powershell_date_to_folder`, do not copy/fork them elsewhere):

1. **`move.ps1`** — recursively scans `-Source`, sorts files into
   `-Dest\yyyy\MM\dd\...` folders by `LastWriteTime` (defaults; see the
   script's `$FolderByAttribute` / `$AttributeDetailLevel` config block for
   other granularities). Dry-run by default.
2. **`GetFoldersAtDepth.ps1`** — walks `-BaseDirPath`, and 7z-archives every
   folder found at exactly `-Depth` levels down into `-OutPath\<relative-path
   with \ replaced by ->.7z`. Its own `Write-Host` of the 7z command line
   already redacts the password (`-p********`) regardless of how the
   password is supplied — safe to let its output print.

The archive password comes from a Bitwarden item via the `bwbio` CLI (Windows
Hello-gated), not an interactive `Read-Host`. Bitwarden item id for this
pipeline: `b370ad8e-8739-4ba5-8f9f-b21e00f4e9bc`.

## Procedure

1. **Ask the user for**, if not already given: `-Source` (messy folder),
   `-Dest` for the organized tree, and `-OutPath` for the resulting `.7z`
   files. Archive `-Depth` is locked to `2` (yyyy/MM, will overwrite one `.7z` per month)
   — don't ask about it, don't offer other granularities.

2. **Dry-run the sort** to sanity-check what would move, before touching anything:
   ```powershell
   & D:\source\Powershell_date_to_folder\move.ps1 -Source <MessySource> -Dest <OrganizedDest> -IsVerbose
   ```
   Read the summary (`N files would be moved`). If the count or sample paths
   look wrong, stop and reconsider `-Source`/`-Dest` before continuing.

3. **Confirm with the user, then execute the sort:**
   ```powershell
   & D:\source\Powershell_date_to_folder\move.ps1 -Source <MessySource> -Dest <OrganizedDest> -Execute -IsVerbose
   ```
   `<OrganizedDest>` must differ from `<MessySource>` — the script does not
   reorganize a folder in place. Verify against the filesystem afterward
   (`Get-ChildItem -Recurse -File` counts on both sides), not just the
   script's own printed total.

4. **Stop here and wait for the user to say "go."** The next step needs the
   user physically present to answer the Windows Hello prompt `bwbio` raises.
   Don't call `bwbio` before they've told you to.

5. **Once told to go, fetch the password and archive**, all in one
   PowerShell invocation so the plaintext password only ever exists in a
   local variable — never `Write-Host` it, never let it appear in a command
   you echo back:
   ```powershell
   $Password = (bwbio get password b370ad8e-8739-4ba5-8f9f-b21e00f4e9bc)
   if ([string]::IsNullOrEmpty($Password)) {
     Write-Host "ABORT: password retrieval failed (empty). Ask the user to retry the Windows Hello prompt."
   } else {
     & D:\source\Powershell_date_to_folder\GetFoldersAtDepth.ps1 -BaseDirPath <OrganizedDest> -OutPath <ArchiveOut> -Depth 3 -InsecurelySupplyPassword $Password
   }
   Remove-Variable Password -ErrorAction SilentlyContinue
   ```
   `bwbio` is flaky under repeated/rapid calls — it can silently deny the
   biometric prompt and fall through to an interactive master-password
   prompt that hangs in a non-interactive shell. If that happens (the call
   errors or `$Password` comes back empty), just retry the fetch once; don't
   loop on it repeatedly.

6. **Verify the archives against disk**, not just each archive's own
   "Everything is Ok" line — re-fetch the password once, then test all of
   them in one pass:
   ```powershell
   $Password = (bwbio get password b370ad8e-8739-4ba5-8f9f-b21e00f4e9bc)
   $archives = Get-ChildItem <ArchiveOut> -Filter *.7z
   $failures = @()
   foreach ($a in $archives) {
     $out = (& 7z t $a.FullName "-p$Password" 2>&1) -join "`n"   # join before matching — 7z t's
                                                                   # multi-line output as an array makes
                                                                   # `$out -notmatch ...` always truthy
     if ($out -notmatch 'Everything is Ok') { $failures += $a.Name }
   }
   "Tested: $($archives.Count), Failures: $($failures.Count)"
   if ($failures.Count -gt 0) { $failures }
   Remove-Variable Password -ErrorAction SilentlyContinue
   ```
   Cross-check `$archives.Count` and the summed file counts 7z reported
   during archiving against the organized-tree file count from step 3 — they
   should match exactly.

## Notes

- `7z` (7-Zip CLI) and `bwbio` must be on `PATH`; the Bitwarden vault must
  already be unlocked (or unlockable via Windows Hello) for the user running
  the archive step.
- `GetFoldersAtDepth.ps1` creates `-OutPath` if missing but does not skip
  existing archives (the skip-if-exists check is commented out in the
  script) — re-running overwrites/re-adds into existing `.7z` files.
- Neither script deletes source files: `move.ps1` moves them into the sorted
  tree (so the messy source folder ends up empty of files, though empty
  subfolder skeletons remain), and archiving reads from the sorted tree
  without removing it.
- In case `bwbio` is unavailable, ask user to `bw unlock` first. Use `bw list items`
  to fetch passwords manually if needed, but avoid storing them in plaintext anywhere.
