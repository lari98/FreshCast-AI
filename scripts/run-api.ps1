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
    python -m venv $venv
}
$py = "$venv\Scripts\python.exe"
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet -e "$repo\packages\forecasting" -e "$repo\apps\api"

$env:FRESHCAST_ENV = "local"
$env:FRESHCAST_DATABASE_URL = "sqlite+pysqlite:///C:/dev/freshcast_local.db"
Write-Host "API: http://localhost:8000/docs  (stop with Ctrl+C)"
& $py -m uvicorn --factory freshcast_api.main:app_factory --port 8000
