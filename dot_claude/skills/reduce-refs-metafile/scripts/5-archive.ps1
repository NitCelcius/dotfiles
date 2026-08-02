<#
.SYNOPSIS  Zip each project idle >= ArchiveDays to an OFF-DRIVE archive root, then
           verify each zip. Non-destructive: originals are NOT deleted here (see
           6-remove-archived.ps1). Archives KEEP .git history but EXCLUDE
           regenerable dirs (node_modules, venvs, framework/Unity caches) so a
           restored project just needs a reinstall. Writes archive-manifest.csv.
.EXAMPLE   pwsh -File 5-archive.ps1 -Root D:\source -ArchiveDays 180 `
             -ArchiveRoot C:\Users\me\DevDrive-Archive -WorkDir C:\temp\refs
#>
param(
  [string]$Root = 'D:\source',
  [int]$ArchiveDays = 180,
  [Parameter(Mandatory)][string]$ArchiveRoot,   # MUST be on a different volume than $Root
  [string]$WorkDir = "$env:TEMP\refs-metafile",
  [string]$SevenZip = 'C:\Program Files\7-Zip\7z.exe'
)
if (-not (Test-Path $SevenZip)) { throw "7-Zip not found at $SevenZip" }
$activity = Join-Path $WorkDir 'activity.csv'
if (-not (Test-Path $activity)) { throw "Run 2-activity.ps1 first ($activity missing)" }
New-Item -ItemType Directory -Force -Path $ArchiveRoot | Out-Null
$log = Join-Path $WorkDir 'archive.log'; "" | Set-Content $log

$excludes = @('node_modules','.venv','venv','__pycache__','.pytest_cache','.mypy_cache',
  '.turbo','.next','.nuxt','.output','.svelte-kit','Library','Logs','.gradle') | % { "-xr!$_" }
$opt=[System.IO.EnumerationOptions]::new(); $opt.RecurseSubdirectories=$true
$opt.IgnoreInaccessible=$true; $opt.AttributesToSkip=[System.IO.FileAttributes]::ReparsePoint

$rows = Import-Csv $activity | ? { [int]$_.IdleDays -ge $ArchiveDays }
$results = New-Object System.Collections.Generic.List[object]
foreach ($r in $rows) {
  $src = Join-Path $Root $r.Name
  $zip = Join-Path $ArchiveRoot "$($r.Name).zip"
  if (-not (Test-Path -LiteralPath $src)) { "MISS $($r.Name)" | Add-Content $log; continue }
  $fc=0; try { $fc=([System.IO.Directory]::EnumerateFiles($src,'*',$opt)|Measure-Object).Count } catch {}
  if ($fc -eq 0) { "EMPTY-SKIP $($r.Name)" | Add-Content $log
    $results.Add([PSCustomObject]@{Name=$r.Name;IdleDays=$r.IdleDays;OrigFiles=0;ZipMB=0;Verify='EMPTY'}); continue }
  if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
  & $SevenZip a -tzip -mx=5 -bso0 -bsp0 $zip $src @excludes | Out-Null; $arc=$LASTEXITCODE
  & $SevenZip t $zip -bso0 -bsp0 | Out-Null; $ver=$LASTEXITCODE
  $mb = if (Test-Path $zip) { [math]::Round((Get-Item $zip).Length/1MB,1) } else { 0 }
  $v = if ($arc -eq 0 -and $ver -eq 0) { 'OK' } else { "FAIL(a=$arc,t=$ver)" }
  "$v $($r.Name) files=$fc zip=${mb}MB" | Add-Content $log
  $results.Add([PSCustomObject]@{Name=$r.Name;IdleDays=$r.IdleDays;OrigFiles=$fc;ZipMB=$mb;Verify=$v})
}
$manifest = Join-Path $WorkDir 'archive-manifest.csv'
$results | Sort-Object {[int]$_.OrigFiles} -Descending | Export-Csv $manifest -NoTypeInformation -Encoding UTF8
$ok=($results|?{$_.Verify -eq 'OK'}).Count
"DONE archives_ok=$ok total_orig_files=$(($results|Measure-Object OrigFiles -Sum).Sum)" | Tee-Object $log -Append | Write-Host
Write-Host "-> manifest: $manifest  (review, then run 6-remove-archived.ps1 -Execute)"