# Run from restaurants-ai-agent folder:
#   .\scripts\run-admin.ps1

$Root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $Root "apps\admin")
Write-Host "Starting Admin UI at http://localhost:5173"
Write-Host "Make sure API is running first: .\scripts\run-api.ps1"
npm run dev
