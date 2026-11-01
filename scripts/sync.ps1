<#
.SYNOPSIS  Commit all changes and push to GitHub in one step.
.EXAMPLE   .\scripts\sync.ps1 "feat: add synthetic data generator"
Uses Conventional Commit messages; refuses to run with an empty message.
#>
param([Parameter(Mandatory = $true)][string]$Message)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
git add -A
if (-not (git status --porcelain)) { Write-Host "Nothing to commit."; exit 0 }
git commit -m $Message
git push origin main
