# Sprint 3+ — download LLM/STT/TTS model weights from Hugging Face (Windows).
# Requires: pip install huggingface_hub  &&  HF_TOKEN in .env or environment
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ModelsDir = if ($env:MODELS_DIR) { $env:MODELS_DIR } else { Join-Path $Root "models" }

$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            Set-Item -Path "env:$($matches[1].Trim())" -Value $matches[2].Trim()
        }
    }
}

if (-not $env:HF_TOKEN) {
    Write-Host "HF_TOKEN is not set. Add it to $EnvFile or set the environment variable."
    Write-Host "Create a Read token at https://huggingface.co/settings/tokens"
    exit 1
}

New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null

Write-Host "Model downloads are stubbed for Sprint 0."
Write-Host "Target directory: $ModelsDir"
Write-Host ""
Write-Host "Planned models (Sprint 3-4):"
Write-Host "  - Qwen/Qwen2.5-14B-Instruct-AWQ   (LLM via vLLM)"
Write-Host "  - openai/whisper-large-v3         (STT)"
Write-Host "  - rhasspy/piper-voices            (TTS)"
Write-Host ""
Write-Host "When ready, uncomment huggingface-cli download commands in scripts/download_models.sh"
Write-Host "Done (stub). No models downloaded yet."
