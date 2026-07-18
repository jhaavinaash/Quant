#Requires -Version 5.1
<#
.SYNOPSIS
  Copy website/dashboard files from Quant repo into your quant-center folder.

.EXAMPLE
  .\scripts\sync_quant_center.ps1 -Target C:\Users\avinaash\quant-center
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Target
)

$ErrorActionPreference = "Stop"
$Source = Split-Path $PSScriptRoot -Parent

$items = @(
    "dashboard",
    "core",
    "alerts",
    "Data",
    "Signals",
    "Portfolio",
    "Engines",
    "logs",
    "config.py",
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "SETUP.md"
)

New-Item -ItemType Directory -Force -Path $Target | Out-Null

foreach ($item in $items) {
    $src = Join-Path $Source $item
    $dst = Join-Path $Target $item
    if (-not (Test-Path $src)) { continue }
    if (Test-Path $src -PathType Container) {
        if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
        Copy-Item $src $dst -Recurse -Force
        Write-Host "Copied folder: $item"
    } else {
        Copy-Item $src $dst -Force
        Write-Host "Copied file: $item"
    }
}

# Exclude large engine price cache from web repo (optional — keeps clone fast)
$engineData = Join-Path $Target "Engines\data"
if (Test-Path $engineData) {
    Get-ChildItem $engineData -Filter "*.csv" -ErrorAction SilentlyContinue | Remove-Item -Force
    Write-Host "Removed Engines\data\*.csv (download again from quant if needed for Run Engines)"
}

Write-Host ""
Write-Host "Done. Next steps:"
Write-Host "  cd $Target"
Write-Host "  git add ."
Write-Host "  git commit -m ""sync from quant"""
Write-Host "  git push"
