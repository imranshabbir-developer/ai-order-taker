# Run from restaurants-ai-agent folder:
#   .\scripts\run-api.ps1

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = Join-Path $Root "packages"
Write-Host "Starting Order API at http://127.0.0.1:8000 (PYTHONPATH=$env:PYTHONPATH)"
python run_api.py
