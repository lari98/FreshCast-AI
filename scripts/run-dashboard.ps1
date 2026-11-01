<#
.SYNOPSIS
  Start the FreshCast dashboard from the latest files of this repository.

.DESCRIPTION
  The project folder name contains "&", which breaks npm scripts on Windows. This
  script therefore mirrors apps\dashboard to C:\dev\dashboard EVERY time (so you
  never run an old copy), clears the Next.js build cache, installs packages when
  they changed, and starts the dev server on http://localhost:3000.

  Usage (from the repository root):  .\scripts\run-dashboard.ps1
  Close any older dashboard window first (Ctrl+C), otherwise the old server keeps
  answering on port 3000.
#>
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repo "apps\dashboard"
$dst = "C:\dev\dashboard"

New-Item -ItemType Directory -Force -Path $dst | Out-Null
# /MIR makes the target an exact copy; node_modules and build folders are kept.
robocopy $src $dst /MIR /XD node_modules .next out /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit code $LASTEXITCODE" }
$global:LASTEXITCODE = 0

if (Test-Path "$dst\.next") { Remove-Item -Recurse -Force "$dst\.next" }
Set-Location $dst

$stamp = Join-Path $dst "node_modules\.package-lock.json"
$lock = Join-Path $dst "package-lock.json"
if (-not (Test-Path $stamp) -or ((Get-Item $lock).LastWriteTime -gt (Get-Item $stamp).LastWriteTime)) {
    npm install --no-audit --no-fund
}

# Shown at the bottom of the page so you can tell which version you are looking at.
$build = "local"
if (Get-Command git -ErrorAction SilentlyContinue) {
    $hash = git -C $repo rev-parse --short HEAD 2>$null
    if ($LASTEXITCODE -eq 0 -and $hash) { $build = $hash }
    $global:LASTEXITCODE = 0
}
$env:NEXT_PUBLIC_BUILD = $build
Write-Host "Dashboard build $build -> http://localhost:3000  (stop with Ctrl+C)"
npm run dev
