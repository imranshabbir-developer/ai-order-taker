# Ollama Desktop Setup (Windows)

This project uses **Ollama only as the LLM API** for text dialogue. You do **not** need the Ollama **Launch** tab (Claude Code, Codex, Pi, etc.).

## 1. Install and run

1. Download from [https://ollama.com/download](https://ollama.com/download)
2. Open the **Ollama** desktop app and leave it running in the background
3. The API listens at `http://127.0.0.1:11434`

## 2. Pull a model

In PowerShell (full path if `ollama` is not on PATH):

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull qwen2.5:7b
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
```

Smaller alternative: `ollama pull qwen2.5:3b`

## 3. Configure `.env`

```env
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen2.5:7b
LLM_API_KEY=not-needed

# Groq still required for voice microphone STT
STT_API_KEY=gsk_your_groq_key_here
```

**Do not duplicate keys** in `.env` — only one `LLM_BASE_URL`, one `ORDER_API_BASE_URL`, etc.

## 4. Start the stack

```powershell
docker compose -f infra/docker-compose.yml up -d
python -m alembic upgrade head
python run_api.py
```

Set `ORDER_API_BASE_URL` to the port printed by `run_api.py` (usually `8080`).

## 5. Verify

```powershell
# Ollama has models
Invoke-RestMethod http://127.0.0.1:11434/api/tags

# Scripted (no LLM)
python scripts/run_scenario_tests.py --mode direct

# Real Ollama LLM
python scripts/run_scenario_tests.py --mode llm --id 02a
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Order API not reachable` | Start `python run_api.py` first |
| `ollama` not recognized in terminal | Use full path under `%LOCALAPPDATA%\Programs\Ollama\` |
| Empty model list | Run `ollama pull qwen2.5:7b` |
| LLM very slow | Normal on CPU; try `qwen2.5:3b` |
| Voice STT fails | Set `STT_API_KEY` to your Groq key |
