#!/usr/bin/env bash
# Sprint 3+ — download LLM/STT/TTS model weights from Hugging Face.
# Requires: pip install huggingface_hub  &&  HF_TOKEN in environment or .env
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELS_DIR="${MODELS_DIR:-$ROOT/models}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "HF_TOKEN is not set. Add it to $ROOT/.env or export it first."
  echo "Create a Read token at https://huggingface.co/settings/tokens"
  exit 1
fi

mkdir -p "$MODELS_DIR"

echo "Model downloads are stubbed for Sprint 0."
echo "Target directory: $MODELS_DIR"
echo ""
echo "Planned models (Sprint 3–4):"
echo "  - Qwen/Qwen2.5-14B-Instruct-AWQ   (LLM via vLLM)"
echo "  - openai/whisper-large-v3         (STT)"
echo "  - rhasspy/piper-voices            (TTS)"
echo ""
echo "When ready, uncomment the huggingface-cli commands below."

# huggingface-cli download Qwen/Qwen2.5-14B-Instruct-AWQ --local-dir "$MODELS_DIR/qwen2.5-14b-awq"
# huggingface-cli download openai/whisper-large-v3 --local-dir "$MODELS_DIR/whisper-large-v3"
# huggingface-cli download rhasspy/piper-voices --local-dir "$MODELS_DIR/piper-voices"

echo "Done (stub). No models downloaded yet."
