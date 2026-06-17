# Run from restaurants-ai-agent folder:
#   .\scripts\run-tests.ps1

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
python run_tests.py @args
