<#
.SYNOPSIS
  Start the FreshCast API locally (needed for the dashboard's "Eigene Daten" upload).

.DESCRIPTION
  Creates a virtual environment in C:\dev\venv-freshcast (a path without "&" or
  spaces, which some Windows tools mishandle), installs the packages from this
  repository, and starts the API on http://localhost:8000. Local mode only:
  header-based sign-in is enabled, so never expose this port to a network.

  Usage (from the repository root):  .\scripts\run-api.ps1
#>
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$venv = "C:\dev\venv-freshcast"

if (-not (Test-Path "$venv\Scripts\python.exe")) {
    New-Item -ItemType Directory -Force -Path "C:\dev" | Out-Null
    # The project needs Python 3.12+. The "py" launcher can pick it even when an
    # older Python is the default on PATH.
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv $venv
        if ($LASTEXITCODE -ne 0) { & py -3 -m venv $venv }
    } else {
        python -m venv $venv
    }
}
$py = "$venv\Scripts\python.exe"
$version = & $py -c "import sys; print(sys.version_info.minor)"
if ([int]$version -lt 12) {
    Remove-Item -Recurse -Force $venv
    throw "Python 3.12 or newer is required. Install it with: winget install Python.Python.3.12  (then open a new PowerShell and run this script again)"
}
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -e "$repo\packages\forecasting" -e "$repo\apps\api"

$env:FRESHCAST_ENV = "local"
$env:FRESHCAST_DATABASE_URL = "sqlite+pysqlite:///C:/dev/freshcast_local.db"
Write-Host "API: http://localhost:8000/docs  (stop with Ctrl+C)"
& $py -m uvicorn --factory freshcast_api.main:app_factory --port 8000
