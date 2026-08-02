<#
.SYNOPSIS  Profile a drive/tree: file+dir counts per top-level child, plus a
           classification of how many files are regenerable cache.
.EXAMPLE   pwsh -File 1-profile.ps1 -Root D:\ -WorkDir C:\temp\refs
#>
param(
  [string]$Root = 'D:\',
  [string[]]$ClassifyRoots,           # subset to deep-classify; default = all children
  [string]$WorkDir = "$env:TEMP\refs-metafile"
)
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null

function Count-Tree($path) {
  # robocopy /L is far faster than Get-ChildItem for pure counting.
  # Summary labels are localized (e.g. Japanese) -> parse by digits, not label text.
  $out = robocopy $path "$WorkDir\__rc_dummy__" /L /E /NFL /NDL /NJH /NP /R:0 /W:0 /XJ
  $f = (($out | Select-String 'ファイル:|Files :' | Select-Object -First 1) -replace '[^\d]',' ' -split '\s+' | ? {$_})[0]
  $d = (($out | Select-String 'ディレクトリ:|Dirs :'  | Select-Object -First 1) -replace '[^\d]',' ' -split '\s+' | ? {$_})[0]
  [PSCustomObject]@{ Files=[int]$f; Dirs=[int]$d }
}

Write-Host "== Per top-level child of $Root =="
$children = Get-ChildItem $Root -Directory -Force -ErrorAction SilentlyContinue
$rows = foreach ($c in $children) {
  $t = Count-Tree $c.FullName
  [PSCustomObject]@{ Name=$c.Name; Files=$t.Files; Dirs=$t.Dirs }
}
$rows | Sort-Object Files -Descending | Format-Table -AutoSize | Out-String | Write-Host

# Deep classification: how much is regenerable cache?
if (-not $ClassifyRoots) { $ClassifyRoots = ($rows | Sort-Object Files -Descending | Select-Object -First 4).Name | % { Join-Path $Root $_ } }
$opt = [System.IO.EnumerationOptions]::new()
$opt.RecurseSubdirectories=$true; $opt.IgnoreInaccessible=$true
$opt.AttributesToSkip=[System.IO.FileAttributes]::ReparsePoint
$cat = [ordered]@{ node_modules=0; git=0; venv=0; pycache=0; buildout=0; unity=0; other=0 }
$total=0
foreach ($r in $ClassifyRoots) {
  if (-not (Test-Path $r)) { continue }
  foreach ($f in [System.IO.Directory]::EnumerateFiles($r,'*',$opt)) {
    $total++
    if ($f -like '*\node_modules\*') { $cat.node_modules++ }
    elseif ($f -like '*\.git\*') { $cat.git++ }
    elseif ($f -like '*\.venv\*' -or $f -like '*\venv\*' -or $f -like '*\site-packages\*') { $cat.venv++ }
    elseif ($f -like '*\__pycache__\*' -or $f -like '*.pyc') { $cat.pycache++ }
    elseif ($f -like '*\Library\*' -or $f -like '*\Temp\*') { $cat.unity++ }
    elseif ($f -like '*\.next\*' -or $f -like '*\.nuxt\*' -or $f -like '*\dist\*' -or $f -like '*\build\*' -or $f -like '*\target\*' -or $f -like '*\.turbo\*') { $cat.buildout++ }
    else { $cat.other++ }
  }
}
Write-Host "== Classification over: $($ClassifyRoots -join ', ') =="
Write-Host "TOTAL $total"
$cat.GetEnumerator() | % { "{0,-14} {1}" -f $_.Key,$_.Value } | Write-Host