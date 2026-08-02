<#
.SYNOPSIS  IRREVERSIBLE. Delete the original project folders that were archived
           with Verify=OK in archive-manifest.csv. Re-verifies each zip's
           integrity immediately before deleting its source. Dry-run by default;
           pass -Execute to delete. Only touches folders whose zip exists AND
           passes 7z t right now.
.EXAMPLE   pwsh -File 6-remove-archived.ps1 -Root D:\source `
             -ArchiveRoot C:\Users\me\DevDrive-Archive -WorkDir C:\temp\refs -Execute
#>
param(
  [string]$Root = 'D:\source',
  [Parameter(Mandatory)][string]$ArchiveRoot,
  [string]$WorkDir = "$env:TEMP\refs-metafile",
  [string]$SevenZip = 'C:\Program Files\7-Zip\7z.exe',
  [switch]$Execute
)
$manifest = Join-Path $WorkDir 'archive-manifest.csv'
if (-not (Test-Path $manifest)) { throw "Run 5-archive.ps1 first ($manifest missing)" }
$empty = Join-Path $WorkDir '__empty__'
$log = Join-Path $WorkDir 'remove-archived.log'; if ($Execute) { "" | Set-Content $log }
$ok = Import-Csv $manifest | ? { $_.Verify -eq 'OK' }
$del=0; $skip=0
foreach ($m in $ok) {
  $src = Join-Path $Root $m.Name
  $zip = Join-Path $ArchiveRoot "$($m.Name).zip"
  if (-not (Test-Path -LiteralPath $src)) { continue }
  if (-not (Test-Path -LiteralPath $zip)) { Write-Host "SKIP(no zip) $($m.Name)"; $skip++; continue }
  & $SevenZip t $zip -bso0 -bsp0 | Out-Null
  if ($LASTEXITCODE -ne 0) { Write-Host "SKIP(zip bad) $($m.Name)"; $skip++; continue }
  if (-not $Execute) { Write-Host "DRY: would delete $src (files=$($m.OrigFiles))"; continue }
  New-Item -ItemType Directory -Force -Path $empty | Out-Null
  $null = robocopy $empty $src /MIR /NFL /NDL /NJH /NJS /NP /R:1 /W:1
  try { Remove-Item -LiteralPath $src -Recurse -Force -ErrorAction Stop; $del++; "DEL $($m.Name)" | Add-Content $log }
  catch { $skip++; "FAIL $($m.Name) :: $($_.Exception.Message)" | Add-Content $log }
}
Remove-Item -LiteralPath $empty -Recurse -Force -ErrorAction SilentlyContinue
if ($Execute) { "DONE deleted=$del skipped=$skip" | Tee-Object $log -Append | Write-Host }
else { Write-Host "DRY RUN complete. Re-run with -Execute to delete $($ok.Count) archived originals." }