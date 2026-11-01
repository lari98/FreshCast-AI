<#
.SYNOPSIS
  Start the FreshCast dashboard and keep it up to date while it runs.

.DESCRIPTION
  The project folder name contains "&", which breaks npm scripts on Windows, so the
  dashboard runs from a mirror at C:\dev\dashboard. This script
    1. stops an OLD dev server that still holds port 3000 (that was the "old version" problem),
    2. mirrors apps\dashboard to C:\dev\dashboard,
    3. installs packages when package-lock.json changed,
    4. starts the dev server, and
    5. keeps mirroring every 2 seconds in the background.
  Step 5 means: after "git pull" (or any change in the repository) the open browser tab
  updates itself through hot reload. You do not stop the server or close the tab.
  Exception: when package.json/package-lock.json change, stop (Ctrl+C) and start again.

  Usage (from the repository root):  .\scripts\run-dashboard.ps1
  Options: -Port 3000  -NoWatch (copy once, no background mirroring)
#>
param([int]$Port = 3000, [switch]$NoWatch)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repo "apps\dashboard"
$dst = "C:\dev\dashboard"

# 1. Free the port if an old Node dev server is still running there.
$old = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $old) {
    $p = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($p -and $p.ProcessName -eq "node") {
        Write-Host "Stopping the old dashboard server (node, pid $procId) on port $Port"
        Stop-Process -Id $procId -Force
    } elseif ($p) {
        throw "Port $Port is used by '$($p.ProcessName)', not by a dashboard. Use -Port 3001."
    }
}

# 2. Mirror. /MIR makes the target an exact copy; generated folders and files are kept.
function Sync-Dashboard {
    robocopy $src $dst /MIR /XD node_modules .next out /XF version.json /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed with exit code $LASTEXITCODE" }
    $global:LASTEXITCODE = 0
}
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Sync-Dashboard
if (Test-Path "$dst\.next") { Remove-Item -Recurse -Force "$dst\.next" }
Set-Location $dst

# 3. Packages.
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

# 5. Background mirroring (a job dies with this window, so nothing is left running).
$job = $null
if (-not $NoWatch) {
    $job = Start-Job -ArgumentList $src, $dst -ScriptBlock {
        param($s, $d)
        while ($true) {
            robocopy $s $d /MIR /XD node_modules .next out /XF version.json /NFL /NDL /NJH /NJS /NP | Out-Null
            Start-Sleep -Seconds 2
        }
    }
    Write-Host "Live update is ON: changes in the repository appear in the open tab by themselves."
}

# 4. Start.
Write-Host "Dashboard build $build -> http://localhost:$Port  (stop with Ctrl+C)"
try {
    npm run dev -- --port $Port
} finally {
    if ($job) { Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -Force -ErrorAction SilentlyContinue }
}
