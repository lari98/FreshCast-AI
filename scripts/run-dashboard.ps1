<#
.SYNOPSIS
  Start the FreshCast dashboard (fast mode by default) and keep it up to date.

.DESCRIPTION
  The project folder name contains "&", which breaks npm scripts on Windows, so the
  dashboard runs from a mirror at C:\dev\dashboard.

  FAST mode (default): builds the production site once and serves it. It starts in
  about a second and every tab opens quicker than in dev mode (measured: first load
  11 s in dev mode against 0.4 s in fast mode).
  DEV mode (-Dev): Next.js hot reload, for editing the dashboard code. Slower.

  In both modes the script
    1. stops an OLD server that still holds the port (the cause of "old version"),
    2. mirrors apps\dashboard to C:\dev\dashboard,
    3. installs packages when package-lock.json changed,
    4. keeps mirroring every 2 seconds in the background. In fast mode a change
       triggers a rebuild, and the open browser tab then reloads itself (it checks
       version.json). You do not close anything. Exception: when package.json or
       package-lock.json change, stop (Ctrl+C) and start again.

  Usage (repository root):  .\scripts\run-dashboard.ps1 [-Dev] [-Port 3000] [-NoWatch]
#>
param([int]$Port = 3000, [switch]$Dev, [switch]$NoWatch)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repo "apps\dashboard"
$dst = "C:\dev\dashboard"

# 1. Free the port if an old Node server is still running there.
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
    $code = $LASTEXITCODE
    if ($code -ge 8) { throw "robocopy failed with exit code $code" }
    $global:LASTEXITCODE = 0
    return $code
}
New-Item -ItemType Directory -Force -Path $dst | Out-Null
$null = Sync-Dashboard
if (Test-Path "$dst\.next") { Remove-Item -Recurse -Force "$dst\.next" }
Set-Location $dst

# 3. Packages.
$stamp = Join-Path $dst "node_modules\.package-lock.json"
$lock = Join-Path $dst "package-lock.json"
if (-not (Test-Path $stamp) -or ((Get-Item $lock).LastWriteTime -gt (Get-Item $stamp).LastWriteTime)) {
    npm install --no-audit --no-fund
}

# Shown at the bottom of the page so you can tell which version you are looking at.
$hash = "local"
if (Get-Command git -ErrorAction SilentlyContinue) {
    $h = git -C $repo rev-parse --short HEAD 2>$null
    if ($LASTEXITCODE -eq 0 -and $h) { $hash = $h }
    $global:LASTEXITCODE = 0
}
$env:NEXT_PUBLIC_BUILD = "$hash+$(Get-Date -Format HHmm)"

$job = $null
try {
    if ($Dev) {
        if (-not $NoWatch) {
            $job = Start-Job -ArgumentList $src, $dst -ScriptBlock {
                param($s, $d)
                while ($true) {
                    robocopy $s $d /MIR /XD node_modules .next out /XF version.json /NFL /NDL /NJH /NJS /NP | Out-Null
                    Start-Sleep -Seconds 2
                }
            }
        }
        Write-Host "DEV mode, build $env:NEXT_PUBLIC_BUILD -> http://localhost:$Port (Ctrl+C to stop)"
        npm run dev -- --port $Port
    } else {
        Write-Host "Building the fast production site (about 30 seconds the first time)..."
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "build failed" }
        if (-not $NoWatch) {
            $job = Start-Job -ArgumentList $src, $dst, $repo -ScriptBlock {
                param($s, $d, $r)
                while ($true) {
                    robocopy $s $d /MIR /XD node_modules .next out /XF version.json /NFL /NDL /NJH /NJS /NP | Out-Null
                    if ($LASTEXITCODE -ge 1 -and $LASTEXITCODE -lt 8) {
                        Set-Location $d
                        $h = git -C $r rev-parse --short HEAD 2>$null
                        $env:NEXT_PUBLIC_BUILD = "$h+$(Get-Date -Format HHmm)"
                        npm run build *> $null   # open tabs notice version.json and reload
                    }
                    Start-Sleep -Seconds 2
                }
            }
            Write-Host "Live update is ON: a change in the repository is rebuilt and the open tab reloads itself."
        }
        Write-Host "FAST mode, build $env:NEXT_PUBLIC_BUILD -> http://localhost:$Port (Ctrl+C to stop)"
        node scripts/static-server.mjs out $Port
    }
} finally {
    if ($job) { Stop-Job $job -ErrorAction SilentlyContinue; Remove-Job $job -Force -ErrorAction SilentlyContinue }
}
