<#
.SYNOPSIS
  Renames items in the source folder per an approved plan CSV, then writes
  an executor-ready plan.

.DESCRIPTION
  Reads a plan CSV (columns: Name, Destination, NewName). For each row with
  a NewName, renames the item in -SourceDir in place. Never overwrites: if
  the target name exists, the row is reported and left unrenamed. Writes
  <PlanCsv basename>-exec.csv (Name = the post-rename name, Destination)
  beside the plan, ready for execute-move.ps1, and renames.csv with the
  per-row result. Run it before execute-move.ps1.

.PARAMETER SourceDir
  Folder the plan's Name column is relative to.

.PARAMETER PlanCsv
  Plan CSV with Name, Destination and optional NewName columns.

.EXAMPLE
  .\apply-renames.ps1 -SourceDir "C:\Users\me\Downloads" -PlanCsv "C:\scratch\plan.csv"
#>
param(
    [Parameter(Mandatory)] [string]$SourceDir,
    [Parameter(Mandatory)] [string]$PlanCsv
)

$reportDir = Split-Path -Parent $PlanCsv
$execCsv = Join-Path $reportDir ((Get-Item -LiteralPath $PlanCsv).BaseName + '-exec.csv')
$plan = Import-Csv -LiteralPath $PlanCsv -Encoding UTF8
$renames = New-Object System.Collections.Generic.List[object]

$exec = foreach ($row in $plan) {
    $name = $row.Name
    if ($row.NewName) {
        $src = Join-Path $SourceDir $row.Name
        $dst = Join-Path $SourceDir $row.NewName
        $result = if (-not (Test-Path -LiteralPath $src)) { 'source missing' }
                  elseif (Test-Path -LiteralPath $dst) { 'target exists, not renamed' }
                  else { 'renamed' }
        if ($result -eq 'renamed') {
            try { Rename-Item -LiteralPath $src -NewName $row.NewName -ErrorAction Stop; $name = $row.NewName }
            catch { $result = "failed: $($_.Exception.Message)" }
        }
        $renames.Add([PSCustomObject]@{ Name = $row.Name; NewName = $row.NewName; Result = $result }) | Out-Null
    }
    [PSCustomObject]@{ Name = $name; Destination = $row.Destination }
}

$renames | Export-Csv -LiteralPath (Join-Path $reportDir 'renames.csv') -NoTypeInformation -Encoding UTF8
$exec | Export-Csv -LiteralPath $execCsv -NoTypeInformation -Encoding UTF8

$renames | Group-Object Result | ForEach-Object { Write-Output ("{0}: {1}" -f $_.Name, $_.Count) }
$renames | Where-Object Result -ne 'renamed' | ForEach-Object { Write-Output "  $($_.Name) -> $($_.NewName): $($_.Result)" }
Write-Output "Executor plan: $execCsv"
