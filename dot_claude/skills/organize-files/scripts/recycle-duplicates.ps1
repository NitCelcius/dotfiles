<#
.SYNOPSIS
  Sends approved byte-identical duplicates in the source folder to the
  Recycle Bin, after re-hashing each against its surviving copy.

.DESCRIPTION
  Reads a CSV (columns: Name, SurvivingCopy). Name is an item in -SourceDir;
  SurvivingCopy is the full path of the copy that stays. An item is
  recycled only if both files exist and their SHA256 hashes match; any
  mismatch or missing file is reported and nothing is removed. Writes
  recycled.csv (Name, Result) beside the list. Use only for a list the
  user approved item by item.

.PARAMETER SourceDir
  Folder the CSV's Name column is relative to.

.PARAMETER ListCsv
  CSV with Name and SurvivingCopy (full path) columns.

.EXAMPLE
  .\recycle-duplicates.ps1 -SourceDir "C:\Users\me\Downloads" -ListCsv "C:\scratch\duplicates.csv"
#>
param(
    [Parameter(Mandatory)] [string]$SourceDir,
    [Parameter(Mandatory)] [string]$ListCsv
)

Add-Type -AssemblyName Microsoft.VisualBasic
$rows = Import-Csv -LiteralPath $ListCsv -Encoding UTF8

$results = foreach ($row in $rows) {
    $src = Join-Path $SourceDir $row.Name
    $surv = $row.SurvivingCopy
    if (-not (Test-Path -LiteralPath $src)) { [PSCustomObject]@{ Name = $row.Name; Result = 'source missing' }; continue }
    if (-not (Test-Path -LiteralPath $surv)) { [PSCustomObject]@{ Name = $row.Name; Result = 'survivor missing, kept' }; continue }
    $srcHash = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
    $survHash = (Get-FileHash -LiteralPath $surv -Algorithm SHA256).Hash
    if ($srcHash -ne $survHash) { [PSCustomObject]@{ Name = $row.Name; Result = 'hash mismatch, kept' }; continue }
    [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($src, 'OnlyErrorDialogs', 'SendToRecycleBin')
    [PSCustomObject]@{ Name = $row.Name; Result = "recycled (sha256 $($srcHash.Substring(0, 12)))" }
}

$results | Export-Csv -LiteralPath (Join-Path (Split-Path -Parent $ListCsv) 'recycled.csv') -NoTypeInformation -Encoding UTF8
$results | ForEach-Object { Write-Output ("{0}  <-  {1}" -f $_.Result, $_.Name) }
