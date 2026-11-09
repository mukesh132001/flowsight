# One-time: publish FlowSight to your GitHub.
#   1. installs git and the GitHub CLI with winget if they are missing, and signs you in once
#   2. moves the CI workflows from _github into .github
#   3. creates the public repo and pushes
#   4. turns on GitHub Pages and deploys the dashboard in site/
#   5. opens the sprint backlog as issues
#
# Run in PowerShell from this folder (Documents\barclays-projects\flowsight):
#   powershell -ExecutionPolicy Bypass -File scripts\publish-github.ps1
# Safe to re-run: it pushes new commits and skips anything that already exists.
param([string]$RepoName = "flowsight", [string]$Message = "")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)          # always work from the repo root

function Invoke-Native([scriptblock]$Command, [switch]$AllowFail) {
    # git / gh write progress to stderr; don't let Windows PowerShell treat that as an error.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try { & $Command } finally { $ErrorActionPreference = $prev }
    if (-not $AllowFail -and $LASTEXITCODE -ne 0) { throw "Failed (exit $LASTEXITCODE): $Command" }
    return ($LASTEXITCODE -eq 0)
}

function Install-IfMissing([string]$Name, [string]$WingetId) {
    if (Get-Command $Name -ErrorAction SilentlyContinue) { return }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "$Name is not installed and winget is not available. Install $WingetId, reopen PowerShell and re-run."
    }
    Write-Host "Installing $Name ($WingetId) with winget (approve the Windows prompt if one appears)..."
    $ErrorActionPreference = "Continue"
    winget install --id $WingetId -e --source winget --accept-source-agreements --accept-package-agreements
    $ErrorActionPreference = "Stop"
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name was installed but is not on PATH yet. Open a new PowerShell window and re-run this script."
    }
}

Install-IfMissing git "Git.Git"
Install-IfMissing gh "GitHub.cli"

# No keyboard prompts anywhere: every gh command gets its answers from flags.
$env:GH_PROMPT_DISABLED = "1"

# Sign in once (browser device flow). The token needs the 'workflow' scope to push .github/workflows.
$ErrorActionPreference = "Continue"
$clipLogin = @(); $clipRefresh = @()       # --clipboard copies the one-time code (newer gh versions)
if ((gh auth login --help 2>&1 | Out-String) -match "--clipboard") { $clipLogin = @("--clipboard") }
if ((gh auth refresh --help 2>&1 | Out-String) -match "--clipboard") { $clipRefresh = @("--clipboard") }
$ErrorActionPreference = "Stop"
function Show-SignInHelp {
    Write-Host ""
    Write-Host "== GitHub sign-in ==  A browser tab is opening at github.com/login/device."
    Write-Host "   Type the one-time code shown below into that page (it is also on your clipboard),"
    Write-Host "   then click Continue and Authorize. This window carries on by itself afterwards."
    Write-Host ""
    Start-Process "https://github.com/login/device"
}
if (-not (Invoke-Native { gh auth status *> $null } -AllowFail)) {
    Show-SignInHelp
    $ErrorActionPreference = "Continue"
    gh auth login --hostname github.com --web --git-protocol https --scopes workflow @clipLogin
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -ne 0) { throw "GitHub sign-in did not complete. Re-run the script to try again." }
}
$ErrorActionPreference = "Continue"
$authInfo = (gh auth status 2>&1 | Out-String)
$ErrorActionPreference = "Stop"
if ($authInfo -notmatch "workflow") {
    Write-Host "Your GitHub sign-in needs the 'workflow' permission to push the CI files."
    Show-SignInHelp
    $ErrorActionPreference = "Continue"
    gh auth refresh --hostname github.com --scopes workflow @clipRefresh
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -ne 0) { throw "Could not add the workflow permission. Re-run the script to try again." }
}
Invoke-Native { gh auth setup-git --hostname github.com } | Out-Null     # git push uses the same sign-in

$owner = (gh api user --jq .login).Trim()
$full = "$owner/$RepoName"
Write-Host "Publishing to https://github.com/$full"

# CI workflows ship in _github (protected paths can't be written remotely)
if (Test-Path "_github") {
    New-Item -ItemType Directory -Force ".github" | Out-Null
    Copy-Item "_github\*" ".github" -Recurse -Force
    Remove-Item "_github" -Recurse -Force
}

# Commit. If git has no identity yet, use your GitHub name and private no-reply e-mail for this repo.
if (-not (Test-Path ".git")) { Invoke-Native { git init -b main } | Out-Null }
if (-not (git config user.email)) {
    $id = (gh api user --jq .id).Trim()
    git config user.email "$id+$owner@users.noreply.github.com"
}
if (-not (git config user.name)) { git config user.name ((gh api user --jq '.name // .login').Trim()) }
Invoke-Native { git add -A } | Out-Null
if (git status --porcelain) {
    # message: -Message, else .commit-msg (git-ignored, removed after use), else a summary of what changed
    if ($Message) {
        Invoke-Native { git commit -q -m $Message } | Out-Null
    } elseif (Test-Path ".commit-msg") {
        Invoke-Native { git commit -q -F ".commit-msg" } | Out-Null
    } elseif (-not (Invoke-Native { git rev-parse --verify -q HEAD *> $null } -AllowFail)) {
        Invoke-Native { git commit -q -m "FlowSight: distribution intelligence for an asset manager" } | Out-Null
    } else {
        $areas = @(git diff --cached --name-only | ForEach-Object {
            $p = $_ -split "/"
            if ($p[0] -eq ".github") { "CI" } elseif ($p[0] -eq "src" -and $p.Count -gt 2) { $p[2] -replace "\.py$", "" }
            elseif ($p.Count -gt 1) { $p[0] } else { $_ }
        } | Select-Object -Unique)
        Invoke-Native { git commit -q -m ("Update " + ($areas -join ", ")) } | Out-Null
    }
}
if (Test-Path ".commit-msg") { Remove-Item ".commit-msg" -Force }

# Create the repo (or push to it if it already exists)
$desc = "Asset-management distribution analytics: PySpark/SQL pipeline, KPI framework, next-best-action ML, GenAI call-prep briefs, Excel/PowerPoint/Tableau outputs"
if (Invoke-Native { gh repo view $full *> $null } -AllowFail) {
    if (-not (git remote)) { Invoke-Native { git remote add origin "https://github.com/$full.git" } | Out-Null }
    Invoke-Native { git push -u origin main } | Out-Null
} else {
    Invoke-Native { gh repo create $RepoName --public --source . --remote origin --push --description $desc } | Out-Null
}
Invoke-Native { gh repo edit $full --homepage "https://$owner.github.io/$RepoName/" --add-topic "data-analytics,pyspark,sql,business-intelligence,machine-learning,asset-management,kpi,genai" } -AllowFail | Out-Null

# GitHub Pages for the dashboard (the Pages workflow only deploys once this flag is set)
Invoke-Native { gh api -X POST "repos/$full/pages" -f build_type=workflow *> $null } -AllowFail | Out-Null
Invoke-Native { gh variable set PAGES_ENABLED --body true --repo $full } | Out-Null
$deployed = $false
for ($i = 0; $i -lt 6 -and -not $deployed; $i++) {
    Start-Sleep -Seconds 5
    $deployed = Invoke-Native { gh workflow run pages.yml --repo $full *> $null } -AllowFail
}
if (-not $deployed) { Write-Host "Pages: run the 'Dashboard on GitHub Pages' workflow from the Actions tab once." }

# Backlog issues (only the first time)
$existing = gh issue list --repo $full --state all --limit 1 --json number | ConvertFrom-Json
if (-not $existing) { & powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\create-issues.ps1" -Repo $full }

Write-Host ""
Write-Host "Done."
Write-Host "  Repo:       https://github.com/$full"
Write-Host "  CI:         https://github.com/$full/actions"
Write-Host "  Dashboard:  https://$owner.github.io/$RepoName/   (live a minute after the Pages run finishes)"
Write-Host ""
Write-Host "Latest workflow runs:"
Start-Sleep -Seconds 5
$ErrorActionPreference = "Continue"
gh run list --repo $full --limit 5
