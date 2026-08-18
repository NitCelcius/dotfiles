<#
.SYNOPSIS  Delete the dirs listed in purge-targets.txt. Uses robocopy empty-mirror
           (fast, handles >260-char paths that 'rd' chokes on), then removes the
           empty shell. Dry-run by default; pass -Execute to actually delete.
.EXAMPLE   pwsh -File 4-purge.ps1 -WorkDir C:\temp\refs            # dry run
           pwsh -File 4-purge.ps1 -WorkDir C:\temp\refs -Execute   # delete
#>
param(
  [string]$WorkDir = "$env:TEMP\refs-metafile",
  [switch]$Execute
)
$list = Join-Path $WorkDir 'purge-targets.txt'
if (-not (Test-Path $list)) { throw "Run 3-find-purge-targets.ps1 first ($list missing)" }
$targets = Get-Content $list | ? { $_.Trim() -ne '' }
if (-not $Execute) {
  Write-Host "DRY RUN - $($targets.Count) dirs would be deleted:"
  $targets | Write-Host
  Write-Host "Re-run with -Execute to delete."
  return
}
$empty = Join-Path $WorkDir '__empty__'
New-Item -ItemType Directory -Force -Path $empty | Out-Null
$log = Join-Path $WorkDir 'purge.log'; "" | Set-Content $log
$i=0; $done=0; $fail=0
foreach ($t in $targets) {
  $i++
  if (-not (Test-Path -LiteralPath $t)) { "SKIP(absent) $t" | Tee-Object -FilePath $log -Append | Write-Host; continue }
  $null = robocopy $empty $t /MIR /NFL /NDL /NJH /NJS /NP /R:1 /W:1
  try { Remove-Item -LiteralPath $t -Recurse -Force -ErrorAction Stop; $done++; "[$i/$($targets.Count)] OK $t" | Tee-Object -FilePath $log -Append | Write-Host }
  catch { $fail++; "[$i/$($targets.Count)] FAIL $t :: $($_.Exception.Message)" | Tee-Object -FilePath $log -Append | Write-Host }
}
Remove-Item -LiteralPath $empty -Recurse -Force -ErrorAction SilentlyContinue
"DONE removed=$done failed=$fail of $($targets.Count)" | Tee-Object -FilePath $log -Append | Write-Host