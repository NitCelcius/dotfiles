# UTF-8 console without spawning chcp.exe (~100 ms)
try { [Console]::OutputEncoding = [Console]::InputEncoding = [System.Text.UTF8Encoding]::new() }
catch { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new() }

# git-completion dot-sources 68 files (~900 ms); defer it until the first completion
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
