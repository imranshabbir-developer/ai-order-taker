# LLM Configuration — Sprint 3.8

## Recommended models (MVP)

| Provider | Model | Use case | Env vars |
|----------|-------|----------|----------|
| **Groq** (default) | `llama-3.1-8b-instant` | Local dev, fast tool calling | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` |
| **Ollama** | `qwen2.5:7b` | Offline dev | `LLM_BASE_URL=http://127.0.0.1:11434/v1` |
| **vLLM / RunPod** | `Qwen/Qwen2.5-7B-Instruct-AWQ` | Production-quality tuning | GPU pod on port 8001 |

## Target

Pass **12+/14** dialogue scenarios in `--mode llm` (see `scripts/run_scenario_tests.py`).

Direct/scripted mode must stay **14/14** for CI.

## Tuning checklist

1. Set `ORDER_API_BASE_URL` to match running API port (8080 or 8000).
2. Run single scenario: `python scripts/run_scenario_tests.py --mode llm --id 04`
3. On `tool_use_failed`, prompts in `config/restaurants/*/prompts.yaml` are adjusted — never paraphrase `item_term`.
4. Lower temperature via provider if supported; Groq uses model defaults.
5. If VRAM tight on GPU pod, use **7B AWQ** before 14B.

## Fallback order

```
Groq llama-3.1-8b → Groq llama-3.3-70b (higher accuracy)
→ vLLM Qwen2.5-7B-AWQ → vLLM Qwen2.5-14B-AWQ
```

## Scenarios requiring extra care

| ID | Risk | Mitigation |
|----|------|------------|
| 04 | Split lines | Two separate `add_item` calls |
| 05 | Violation detection | Single tool call, read engine message |
| 11 | Pronunciation | Use exact terms; ASR aliases in `pronunciations.json` |
| 12 | Payment | Checkout via LLM; card via `/orders/{id}/payment` only |

## Voice stack (Sprint 4)

- STT: Groq Whisper (`STT_MODEL=whisper-large-v3`)
- TTS: Edge (`TTS_VOICE=en-US-JennyNeural`) — swap to Piper when GPU pod ready
- VAD: energy-based MVP; Silero when `models/` downloaded via `scripts/download_models.sh`
