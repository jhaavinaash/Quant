#Requires -Version 5.1
<#
.SYNOPSIS
  Copy the complete Quant-Center website package to your quant-center folder and push to GitHub.

.EXAMPLE
  cd C:\Users\avinaash\quant
  .\scripts\publish_quant_center.ps1
#>
param(
    [string]$Target = "C:\Users\avinaash\quant-center"
)

$ErrorActionPreference = "Stop"
$QuantRoot = Split-Path $PSScriptRoot -Parent
$Source = Join-Path $QuantRoot "quant-center-publish"
$MarketIntelligenceSource = Join-Path $QuantRoot "market_intelligence"

if (-not (Test-Path $Source)) {
    Write-Error "quant-center-publish folder not found. Run git pull in quant folder first."
}

if (-not (Test-Path $Target)) {
    Write-Host "Cloning Quant-Center..."
    $parent = Split-Path $Target -Parent
    Set-Location $parent
    git clone https://github.com/jhaavinaash/Quant-Center.git (Split-Path $Target -Leaf)
}

Write-Host "Copying files to $Target ..."
Get-ChildItem $Target -Force | Where-Object { $_.Name -ne '.git' } | Remove-Item -Recurse -Force

$exclude = @('.git', 'node_modules', 'frontend\dist', 'backend\venv', 'venv-streamlit')
Get-ChildItem $Source -Force | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $Target $_.Name) -Recurse -Force
}
if (Test-Path $MarketIntelligenceSource) {
    Copy-Item $MarketIntelligenceSource (Join-Path $Target "market_intelligence") -Recurse -Force
    Write-Host "Copied Market Intelligence package."
}

Set-Location $Target

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host "Created .env — edit with your passwords."
}

Write-Host ""
Write-Host "=== NEXT: push to GitHub (run these commands) ==="
Write-Host "cd $Target"
Write-Host "git add ."
Write-Host "git commit -m ""complete quant-center update from home"""
Write-Host "git push"
Write-Host ""
Write-Host "Then at office: cd C:\Users\dell\quant-center && git pull"
