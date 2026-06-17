# Restaurants AI Agent

Self-hosted AI voice restaurant ordering platform (HOT BAGELS MVP).

## Sprint 0 — Done

- **Order engine** — deterministic menu, cart, modifiers, rules (`packages/order_engine/`)
- **13/13 scenario tests** — HOT BAGELS critical tests pass (`tests/scenarios/`)
- **Order API** — FastAPI REST layer (`apps/order_api/`)
- **Admin UI** — React console for demo & cart inspection (`apps/admin/`)

## Run locally

### 1. Backend tests (no GPU)

```powershell
cd restaurants-ai-agent
pip install -r requirements-dev.txt
python run_tests.py
```
Or: `.\scripts\run-tests.ps1`

### 2. Order API (Terminal 1)

**Option A — recommended (no PYTHONPATH needed):**
```powershell
cd restaurants-ai-agent
python run_api.py
```

**Option B — manual:**
```powershell
cd restaurants-ai-agent
$env:PYTHONPATH="packages"   # note the $ at the start — required in PowerShell
python -m uvicorn apps.order_api.main:app --reload --port 8000
```

### 3. Admin UI (Terminal 2 — start API first)

```powershell
cd restaurants-ai-agent\apps\admin
npm install
npm run dev
```

Or use helper script:
```powershell
.\scripts\run-admin.ps1
```

Open http://localhost:5173 — Dashboard → Run Demo Order → Cart Inspector.

## Project layout

```
restaurants-ai-agent/
├── packages/order_engine/     # Domain — source of truth
├── apps/order_api/            # FastAPI
├── apps/admin/                # React admin console
├── config/restaurants/        # Per-restaurant menu JSON
├── tests/scenarios/           # Client test suite
└── CLIENT_NEEDS.md            # What we need from client
```

## Next sprints

1. **Sprint 1** — Replace draft menu with client's official menu data
2. **Sprint 2** — PostgreSQL order persistence + post-order lookup
3. **Sprint 3** — LLM tool calling (Qwen2.5 + vLLM)
4. **Sprint 4** — Voice pipeline (Pipecat + Whisper + Piper)

See `../IMPLEMENTATION_PLAN.md` for full roadmap.
