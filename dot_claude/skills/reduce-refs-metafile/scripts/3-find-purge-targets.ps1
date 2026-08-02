<#
.SYNOPSIS  From activity.csv, list regenerable cache dirs to delete in projects
           idle >= PurgeDays. Projects newer than that are left fully intact.
           SAFETY: 'Library'/'Temp' are only treated as cache inside a real Unity
           project (sibling 'Assets'+'ProjectSettings'); generic build dir names
           (build/out/dist) are NOT auto-targeted to avoid nuking a source folder.
.EXAMPLE   pwsh -File 3-find-purge-targets.ps1 -Root D:\source -PurgeDays 90 -WorkDir C:\temp\refs
#>
param(
  [string]$Root = 'D:\source',
  [int]$PurgeDays = 90,
  [string]$WorkDir = "$env:TEMP\refs-metafile"
)
$activity = Join-Path $WorkDir 'activity.csv'
if (-not (Test-Path $activity)) { throw "Run 2-activity.ps1 first ($activity missing)" }
$purge = Import-Csv $activity | ? { [int]$_.IdleDays -ge $PurgeDays } | % { $_.Name }
$purgeSet=@{}; $purge | % { $purgeSet[$_]=$true }

$fwCache = @('.next','.nuxt','.output','.svelte-kit','.turbo','.angular','.gradle')
$fwSet=@{}; $fwCache | % { $fwSet[$_.ToLower()]=$true }
$targets = New-Object System.Collections.Generic.List[string]

foreach ($proj in [System.IO.Directory]::GetDirectories($Root)) {
  $pname=[System.IO.Path]::GetFileName($proj)
  if (-not $purgeSet.ContainsKey($pname)) { continue }
  $stack=New-Object System.Collections.Generic.Stack[string]; $stack.Push($proj)
  while ($stack.Count -gt 0) {
    $dir=$stack.Pop()
    $children=@(); try { $children=[System.IO.Directory]::GetDirectories($dir) } catch { continue }
    $names=@{}; foreach ($c in $children) { $names[[System.IO.Path]::GetFileName($c).ToLower()]=$true }
    $isUnity = $names.ContainsKey('assets') -and $names.ContainsKey('projectsettings')
    foreach ($c in $children) {
      $n=[System.IO.Path]::GetFileName($c).ToLower()
      if ([System.IO.File]::GetAttributes($c) -band [System.IO.FileAttributes]::ReparsePoint) { continue }
      if ($n -eq 'node_modules') { $targets.Add($c); continue }
      if ($fwSet.ContainsKey($n)) { $targets.Add($c); continue }
      if ($isUnity -and ($n -in 'library','temp','logs','obj')) { $targets.Add($c); continue }
      $stack.Push($c)
    }
  }
}
$out = Join-Path $WorkDir 'purge-targets.txt'
$targets | Set-Content $out -Encoding UTF8
Write-Host "$($targets.Count) dirs targeted across $($purge.Count) idle(>=$PurgeDays d) projects"
Write-Host "-> $out  (review this file, then run 4-purge.ps1)"