<#
.SYNOPSIS
  Executes an approved organize-files move plan, resiliently.

.DESCRIPTION
  Reads a plan CSV (columns: Name, Destination) and moves each named item
  from -SourceDir into -DestRoot\<Destination>. Never overwrites — a
  same-named item already at the destination is left alone and reported
  as a collision, not clobbered. Per-item failures (locked files, in-use
  by another process, permission errors, etc.) are caught individually so
  one bad file never aborts the rest of the batch. Safe to re-run: items
  already moved (source no longer present) are silently skipped.

  Rows with an empty Destination, or a Destination starting with
  "_needs-review" or "SKIP", are intentionally left in place and counted
  but not itemized — that's how organize-files marks "not approved to
  move yet" in a plan.

.PARAMETER SourceDir
  Folder the plan's Name column is relative to (the folder being organized).

.PARAMETER DestRoot
  Folder the plan's Destination column is relative to.

.PARAMETER PlanCsv
  Path to the plan CSV (Name, Destination columns; extra columns ignored).

.PARAMETER ReportDir
  Where to write moved.csv / collisions.csv / failed.csv. Defaults to the
  PlanCsv's directory.

.EXAMPLE
  .\execute-move.ps1 -SourceDir "C:\Users\me\Downloads" `
                      -DestRoot  "C:\Users\me\OneDrive" `
                      -PlanCsv   "C:\scratch\plan.csv"
#>
param(
    [Parameter(Mandatory)] [string]$SourceDir,
    [Parameter(Mandatory)] [string]$DestRoot,
    [Parameter(Mandatory)] [string]$PlanCsv,
    [string]$ReportDir
)

if (-not $ReportDir) { $ReportDir = Split-Path -Parent $PlanCsv }
if (-not (Test-Path $ReportDir)) { New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null }

$plan = Import-Csv $PlanCsv

$moved = New-Object System.Collections.Generic.List[object]
$collisions = New-Object System.Collections.Generic.List[object]
$failed = New-Object System.Collections.Generic.List[object]
$leftAsIs = 0
$alreadyGone = 0

foreach ($row in $plan) {
    $name = $row.Name
    $destRel = $row.Destination

    if ([string]::IsNullOrWhiteSpace($destRel) -or $destRel -like "_needs-review*" -or $destRel -like "SKIP*") {
        $leftAsIs++
        continue
    }

    $srcPath = Join-Path $SourceDir $name
    if (-not (Test-Path -LiteralPath $srcPath)) {
        # Already moved in a prior run, or never existed - not an error.
        $alreadyGone++
        continue
    }

    $destDir = Join-Path $DestRoot $destRel
    if (-not (Test-Path -LiteralPath $destDir)) {
        try { New-Item -ItemType Directory -Path $destDir -Force -ErrorAction Stop | Out-Null }
        catch {
            $failed.Add([PSCustomObject]@{ Name = $name; Destination = $destRel; Error = "mkdir failed: $($_.Exception.Message)" }) | Out-Null
            continue
        }
    }

    $destPath = Join-Path $destDir (Split-Path -Leaf $srcPath)
    if (Test-Path -LiteralPath $destPath) {
        $collisions.Add([PSCustomObject]@{ Name = $name; Destination = $destRel }) | Out-Null
        continue
    }

    try {
        Move-Item -LiteralPath $srcPath -Destination $destPath -ErrorAction Stop
        $moved.Add([PSCustomObject]@{ Name = $name; Destination = $destRel }) | Out-Null
    } catch {
        # Resilient: one locked/in-use/permission-denied file must not stop the batch.
        $failed.Add([PSCustomObject]@{ Name = $name; Destination = $destRel; Error = $_.Exception.Message }) | Out-Null
    }
}

$moved | Export-Csv -Path (Join-Path $ReportDir "moved.csv") -NoTypeInformation -Encoding UTF8
$collisions | Export-Csv -Path (Join-Path $ReportDir "collisions.csv") -NoTypeInformation -Encoding UTF8
$failed | Export-Csv -Path (Join-Path $ReportDir "failed.csv") -NoTypeInformation -Encoding UTF8

Write-Output "MOVED: $($moved.Count)"
Write-Output "COLLISIONS (already existed at destination, left untouched): $($collisions.Count)"
$collisions | ForEach-Object { Write-Output "  COLLISION: $($_.Name) -> $($_.Destination)" }
Write-Output "FAILED (could not move - see reason): $($failed.Count)"
$failed | ForEach-Object { Write-Output "  FAILED: $($_.Name) -> $($_.Destination) :: $($_.Error)" }
Write-Output "LEFT AS-IS (not approved in this plan): $leftAsIs"
Write-Output "ALREADY GONE (source missing, likely moved in a prior run): $alreadyGone"
Write-Output ""
Write-Output "Reports written to: $ReportDir\{moved,collisions,failed}.csv"
