# Creates the sprint backlog as GitHub issues (publish-github.ps1 calls this once).
# Manual use, from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\create-issues.ps1 -Repo <you>/flowsight
param([string]$Repo = "")
$ErrorActionPreference = "Continue"     # gh writes progress to stderr; check exit codes instead
Set-Location (Split-Path $PSScriptRoot -Parent)
$repoArg = @()
if ($Repo) { $repoArg = @("--repo", $Repo) }
$issues = Get-Content -Raw -Encoding UTF8 "scripts/issues.json" | ConvertFrom-Json
$labels = @($issues | ForEach-Object { $_.m } | Sort-Object -Unique) + @("story")
foreach ($l in $labels) {
    gh label create $l --color "1D76DB" --force @repoArg *> $null
}
# Bodies go through a UTF-8 file: Windows PowerShell mangles quotes in long native arguments.
$utf8 = New-Object System.Text.UTF8Encoding($false)
$tmp = [System.IO.Path]::GetTempFileName()
$made = 0
foreach ($i in $issues) {
    [System.IO.File]::WriteAllText($tmp, $i.body, $utf8)
    gh issue create --title $i.title --body-file $tmp --label $i.m --label "story" @repoArg | Out-Null
    if ($LASTEXITCODE -eq 0) { $made++ } else { Write-Host "Could not create: $($i.title)" }
}
Remove-Item $tmp -ErrorAction SilentlyContinue
Write-Host "Created $made of $($issues.Count) backlog issues."
