<#
.SYNOPSIS  Build the Lambda deployment folder dist\worker (Linux ARM64, Python 3.12).
Run from the repo root before `cdk synth` / `cdk deploy`.
#>
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
Remove-Item -Recurse -Force dist\worker -ErrorAction SilentlyContinue
# Third-party wheels for the Lambda platform (not the local Windows machine).
python -m pip install --target dist\worker --platform manylinux2014_aarch64 `
  --python-version 3.12 --only-binary=:all: --implementation cp `
  "pydantic>=2.7,<3" "pydantic-settings>=2.4" "sqlalchemy>=2.0" "psycopg[binary]>=3.2"
# Our own pure-Python packages (their heavy ML deps are not needed by the worker).
python -m pip install --target dist\worker --no-deps .\packages\forecasting .\apps\api
Write-Host "Built dist\worker"
