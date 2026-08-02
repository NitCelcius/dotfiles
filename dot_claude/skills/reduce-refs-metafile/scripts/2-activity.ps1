<#
.SYNOPSIS  Compute each project's TRUE last-worked date = newest mtime among
           SOURCE files only (cache dirs pruned). Folder mtime is unreliable
           because installs/builds bump it. Output: activity.csv (sorted).
.EXAMPLE   pwsh -File 2-activity.ps1 -Root D:\source -WorkDir C:\temp\refs
#>
param(
  [string]$Root = 'D:\source',
  [string]$WorkDir = "$env:TEMP\refs-metafile"
)
New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
$now = Get-Date
$prune = @('node_modules','.git','Library','Temp','obj','dist','build','.next','target',
  '.gradle','.angular','.venv','venv','env','__pycache__','.pytest_cache','.mypy_cache',
  'site-packages','.turbo','.cache','out','coverage','.nuxt','.output','.svelte-kit','.parcel-cache')
$pruneSet=@{}; $prune | % { $pruneSet[$_.ToLower()]=$true }

$results = New-Object System.Collections.Generic.List[object]
foreach ($proj in [System.IO.Directory]::GetDirectories($Root)) {
  $maxTicks=0L; $srcFiles=0
  $stack = New-Object System.Collections.Generic.Stack[string]; $stack.Push($proj)
  while ($stack.Count -gt 0) {
    $dir = $stack.Pop()
    try {
      foreach ($sub in [System.IO.Directory]::EnumerateDirectories($dir)) {
        $n=[System.IO.Path]::GetFileName($sub).ToLower()
        if ($pruneSet.ContainsKey($n)) { continue }
        if ([System.IO.File]::GetAttributes($sub) -band [System.IO.FileAttributes]::ReparsePoint) { continue }
        $stack.Push($sub)
      }
      foreach ($f in [System.IO.Directory]::EnumerateFiles($dir)) {
        $srcFiles++; $t=[System.IO.File]::GetLastWriteTime($f).Ticks
        if ($t -gt $maxTicks) { $maxTicks=$t }
      }
    } catch {}
  }
  $last = if ($maxTicks -gt 0) { [datetime]::new($maxTicks) } else { (Get-Item $proj).LastWriteTime }
  $results.Add([PSCustomObject]@{
    Name=[System.IO.Path]::GetFileName($proj)
    LastSrcEdit=$last.ToString('yyyy-MM-dd')
    IdleDays=[int]($now-$last).TotalDays
    SrcFiles=$srcFiles
  })
}
$csv = Join-Path $WorkDir 'activity.csv'
$results | Sort-Object IdleDays | Export-Csv $csv -NoTypeInformation -Encoding UTF8
$results | Sort-Object IdleDays | Format-Table -AutoSize | Out-String | Write-Host
Write-Host "-> $csv"