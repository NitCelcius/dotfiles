try { [Console]::OutputEncoding = [Console]::InputEncoding = [System.Text.UTF8Encoding]::new() }
catch { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new() }

Register-ArgumentCompleter -CommandName git -Native -ScriptBlock {
    param($wordToComplete, $CommandAst, $CursorPosition)
    Import-Module git-completion
    Complete-Git -CommandAst $CommandAst -CursorPosition $CursorPosition
}

Register-ArgumentCompleter -CommandName gitk -Native -ScriptBlock {
    param($wordToComplete, $CommandAst, $CursorPosition)
    Import-Module git-completion
    Complete-Gitk -CommandAst $CommandAst -CursorPosition $CursorPosition
}

# I really wanted an alias for this, really
function mklink {
    param(
        [Parameter(Position = 0)][string]$First,
        [Parameter(Position = 1)][string]$Second,
        [Parameter(Position = 2)][string]$Third
    )
    $help = @'
MKLINK [[/D] | [/H] | [/J]] LinkName TargetPath

        /D          Creates a directory symbolic link.  Default is a file
                    symbolic link.
        /H          Creates a hard link instead of a symbolic link.
        /J          Creates a Directory Junction.
        LinkName    Specifies the new symbolic link name.
        TargetPath  Specifies the path (relative or absolute) that the new link
                    refers to.
'@

    if (-not $First -or $First -eq '/?') {
        $help
        return
    }

    $knownFlags = '/D', '/H', '/J'
    if ($First.StartsWith('/') -and $First -notin $knownFlags) {
        Write-Error "mklink: unrecognized option '$First'."
        $help
        return
    }

    $flag, $link, $target = if ($First -in $knownFlags) {
        $First, $Second, $Third
    }
    else {
        $null, $First, $Second
    }

    if (-not $link -or -not $target) {
        $help
        return
    }

    $itemType = switch ($flag) {
        '/H' { 'HardLink' }
        '/J' { 'Junction' }
        default { 'SymbolicLink' }
    }

    New-Item -ItemType $itemType -Path $link -Target $target
}

# Run claude with the 5-minute prompt cache TTL forced (for short sessions).
function claude-short {
    $env:FORCE_PROMPT_CACHING_5M = '1'
    try { claude @args } finally { Remove-Item Env:FORCE_PROMPT_CACHING_5M -ErrorAction SilentlyContinue }
}
