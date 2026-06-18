# Implementation Plan — AI Voice Restaurant Agent

> **Project:** voice-multan (HOT BAGELS MVP → multi-restaurant production)
> **Goal:** Ship a demo-ready, self-hosted voice agent that passes all 14 client test scenarios consistently.
> **Architecture standard:** Clean/hexagonal design, service-oriented monorepo, production-grade from day one.

---

## Table of Contents

1. [Prerequisites & Sign-ups](#1-prerequisites--sign-ups)
2. [Architecture Principles](#2-architecture-principles)
3. [Target System Architecture](#3-target-system-architecture)
4. [Monorepo Structure](#4-monorepo-structure)
5. [Technology Decisions (Locked)](#5-technology-decisions-locked)
6. [Implementation Phases](#6-implementation-phases)
7. [Sprint-by-Sprint Planner](#7-sprint-by-sprint-planner)
8. [Definition of Done per Phase](#8-definition-of-done-per-phase)
9. [Environment Setup Checklist](#9-environment-setup-checklist)
10. [Client Deliverables to Request (Week 1)](#10-client-deliverables-to-request-week-1)
11. [Coding Standards & Practices](#11-coding-standards--practices)
12. [Testing Strategy](#12-testing-strategy)
13. [Deployment & DevOps](#13-deployment--devops)
14. [Risk Register & Blockers](#14-risk-register--blockers)
15. [Day 1 Kickoff — What to Do First](#15-day-1-kickoff--what-to-do-first)

---

## 1. Prerequisites & Sign-ups

Everything below is **free to register** unless marked **(paid)**. No OpenAI / Anthropic / ElevenLabs / Twilio API keys.

### 1.1 Required before coding

| What | Why | Action | Cost |
|------|-----|--------|------|
| **GitHub account** | Source control, CI, issue tracking | [github.com](https://github.com) — create private repo `voice-multan` | Free |
| **Docker Hub account** | Pull/push container images | [hub.docker.com](https://hub.docker.com) | Free |
| **Hugging Face account** | Download Qwen2.5, Whisper, Piper models | [huggingface.co](https://huggingface.co) — accept model licenses | Free |
| **Python 3.11+** | Core runtime | Install locally | Free |
| **Git** | Version control | Install locally | Free |

### 1.2 Required before voice/LLM integration (Week 3–4)

| What | Why | Action | Cost |
|------|-----|--------|------|
| **GPU rental — RunPod** | Run vLLM + faster-whisper without buying hardware | [runpod.io](https://runpod.io) — add payment method, rent RTX 4090 pod on demand | **(paid)** ~$0.30–0.50/hr |
| **GPU rental — Vast.ai** (alternative) | Same purpose, often cheaper spot instances | [vast.ai](https://vast.ai) | **(paid)** ~$0.25–0.45/hr |
| **NVIDIA CUDA Toolkit** | GPU inference | Installed on GPU pod (usually pre-installed on RunPod templates) | Free |

> **Tip:** Only spin up GPU when testing voice pipeline. Order engine runs on CPU with zero GPU cost.

### 1.3 Required before live phone demo (Week 5–6)

| What | Why | Action | Cost |
|------|-----|--------|------|
| **SIP trunk provider** | Real PSTN phone number for client demo | Options: **Telnyx**, **VoIP.ms**, **Twilio SIP** (SIP only, no AI API), or **client provides trunk** | **(paid)** ~$1–5/mo + per-minute |
| **VPS for Asterisk** | Host telephony 24/7 (lightweight) | **Hetzner** CX22 or **DigitalOcean** droplet | **(paid)** ~$5–10/mo |
| **Domain name** (optional) | Professional SIP/WebRTC endpoints | Namecheap / Cloudflare | **(paid)** ~$10/yr |

> **Ask client first:** They may already have a phone system / SIP trunk. Use theirs if possible.

### 1.4 Required before SMS demo (Week 5–6)

| What | Why | Action | Cost |
|------|-----|--------|------|
| **Option A — Client SMS webhook** | Best for production | Ask client for existing SMS provider API docs | Client's cost |
| **Option B — Kannel + GSM modem** | Fully self-hosted, no SaaS API | Buy USB GSM modem + SIM card; install Kannel on VPS | **(paid)** ~$30 hardware + SIM |
| **Option C — MVP mock** | Demo without real SMS | Log SMS to DB + admin panel preview | Free (demo only) |

### 1.5 Required before payment demo (Week 5–6)

| What | Why | Action | Cost |
|------|-----|--------|------|
| **Payment processor** | Real card processing | Client provides **Stripe**, **Square**, or **Authorize.net** sandbox credentials | Client's account |
| **MVP without processor** | Demo secure capture flow | Build mock vault (Luhn check + simulate success/fail) | Free |

> **PCI rule:** Never store raw CVV. Card digits captured in isolated service; LLM never sees them.

### 1.6 Optional but recommended

| What | Why | Cost |
|------|-----|------|
| **Sentry** (self-hosted or free tier) | Error tracking on calls | Free tier available |
| **Grafana Cloud free tier** | Call metrics dashboard | Free |
| **Linear / GitHub Projects** | Sprint task board | Free |
| **1Password / Bitwarden** | Secrets management | Free tier |

### 1.7 Sign-up priority order

```
Day 1:   GitHub + Docker Hub + Hugging Face
Week 1:  RunPod account (add card, don't start pod yet)
Week 4:  SIP trunk OR confirm client provides one
Week 5:  SMS path decided + payment sandbox from client
Week 6:  Hetzner VPS for Asterisk (if not using client infra)
```

---

## 2. Architecture Principles

These rules apply to every file we write.

### 2.1 Clean / Hexagonal Architecture

```
                    ┌─────────────────────────────────┐
  Phone / HTTP ───► │         ADAPTERS (in)           │
                    │  asterisk, pipecat, fastapi     │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │      APPLICATION LAYER          │
                    │  use cases, dialogue manager    │
                    │  (orchestrates, no menu logic)  │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │         DOMAIN LAYER            │
                    │  Order, Cart, Menu, Rules       │
                    │  (pure Python, zero IO)         │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │      ADAPTERS (out)             │
                    │  postgres, redis, sms, payment  │
                    └─────────────────────────────────┘
```

**Rule:** Domain layer has **zero** imports from FastAPI, Pipecat, SQLAlchemy, or LLM SDKs.

### 2.2 Single Source of Truth

| Data | Owner | Consumers |
|------|-------|-----------|
| Cart state | `OrderEngine` (domain) | Voice agent, SMS, payment, DB |
| Spoken confirmation | `Cart.to_spoken_summary()` | TTS only |
| SMS body | `Cart.to_sms_summary()` | SMS gateway only |
| Payment amount | `Cart.total_cents` | Payment service only |

### 2.3 LLM as Interpreter, Not Authority

- LLM calls **tools** → tools call **use cases** → use cases call **domain**
- Domain returns `Success | ClarificationNeeded | RuleViolation`
- Pipeline converts domain results to spoken responses — never free-form LLM confirmation

### 2.4 Configuration over Code

- One restaurant = one config folder (menu, rules, hours, pronunciations)
- Onboarding restaurant #2 = add config folder, zero code changes

### 2.5 Fail-Safe Defaults

- Unknown menu item → ask, never invent
- Ambiguous item → list options, never guess
- 3 failed understanding attempts → escalate to human
- Store closed → polite message + offer callback

### 2.6 Scalability hooks (built in from start)

| Concern | MVP approach | Scale approach |
|---------|--------------|----------------|
| Concurrent calls | Single voice worker | Horizontal Pipecat workers behind Redis queue |
| LLM inference | Single vLLM instance | vLLM replica pool + load balancer |
| Restaurant config | JSON files | Config service + admin API |
| Orders | PostgreSQL | Same DB, read replicas later |
| Telephony | Single Asterisk box | Asterisk cluster or LiveKit SFU |

---

## 3. Target System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL                                       │
│   PSTN Phone ──► SIP Trunk ──► Asterisk ──► audio stream (WebSocket)  │
└────────────────────────────────────────┬────────────────────────────────┘
                                         │
┌────────────────────────────────────────▼────────────────────────────────┐
│  SERVICE: voice-agent (Pipecat)                                          │
│  ┌─────────┐   ┌─────────┐   ┌──────────────┐   ┌─────────┐            │
│  │   VAD   │──►│   STT   │──►│ Dialogue Mgr │──►│   TTS   │            │
│  │ Silero  │   │ whisper │   │ LangGraph    │   │  Piper  │            │
│  └─────────┘   └─────────┘   └──────┬───────┘   └─────────┘            │
│                                     │ tool calls                         │
└─────────────────────────────────────┼───────────────────────────────────┘
                                      │ HTTP (internal)
┌─────────────────────────────────────▼───────────────────────────────────┐
│  SERVICE: order-api (FastAPI)                                            │
│  POST /v1/calls/{id}/tool  →  AddItem, SetModifier, Checkout, etc.      │
│  GET  /v1/calls/{id}/cart  →  current cart snapshot                     │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────────────┐
│  MODULE: order_engine (domain — shared library)                          │
│  MenuCatalog │ Cart │ ModifierRules │ Pricing │ SummaryRenderer         │
└─────────────────────────────────────┬───────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
   ┌─────────────┐           ┌─────────────┐           ┌─────────────┐
   │ PostgreSQL  │           │    Redis    │           │  LLM (vLLM) │
   │ orders,menu │           │ call state  │           │  Qwen2.5    │
   └─────────────┘           └─────────────┘           └─────────────┘

Post-checkout:
   order-api ──► payment-service (isolated)
   order-api ──► sms-gateway
   order-api ──► PostgreSQL (persist order)
```

### Service boundaries (MVP = modular monolith, split later)

| Service | Responsibility | Port |
|---------|----------------|------|
| `order-api` | REST API, use cases, persistence | 8000 |
| `voice-agent` | Pipecat pipeline, calls order-api | — |
| `llm-server` | vLLM OpenAI-compatible endpoint | 8001 |
| `payment-service` | Card capture, tokenization | 8002 |
| `sms-gateway` | Send order SMS | 8003 |
| `asterisk` | Telephony | 5060/8088 |

---

## 4. Monorepo Structure

```
voice-multan/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # lint + test on every PR
│       └── deploy-staging.yml
├── apps/
│   ├── order_api/                 # FastAPI application
│   │   ├── main.py
│   │   ├── routers/
│   │   ├── dependencies/
│   │   └── Dockerfile
│   ├── voice_agent/               # Pipecat pipeline
│   │   ├── pipeline.py
│   │   ├── tools.py               # tool schemas → order-api calls
│   │   ├── prompts/
│   │   └── Dockerfile
│   ├── payment_service/
│   └── sms_gateway/
├── packages/
│   ├── order_engine/              # DOMAIN — pure Python library
│   │   ├── domain/
│   │   │   ├── cart.py
│   │   │   ├── menu.py
│   │   │   ├── rules.py
│   │   │   └── exceptions.py
│   │   ├── services/
│   │   │   ├── add_item.py
│   │   │   ├── checkout.py
│   │   │   └── modify_order.py
│   │   └── renderers/
│   │       ├── spoken.py
│   │       └── sms.py
│   ├── dialogue/                  # LangGraph state machine
│   └── shared/                    # DTOs, logging, config loader
├── config/
│   └── restaurants/
│       └── hot_bagels_2nd_street/
│           ├── menu.json
│           ├── modifiers.json
│           ├── rules.json
│           ├── hours.json
│           ├── pronunciations.json
│           └── prompts.yaml
├── infra/
│   ├── docker-compose.yml         # local full stack
│   ├── docker-compose.gpu.yml     # GPU overlay
│   ├── asterisk/
│   └── k8s/                       # future — empty for MVP
├── tests/
│   ├── unit/                      # domain tests (no IO)
│   ├── integration/               # order-api tests
│   ├── scenarios/                 # 14 HOT BAGELS tests
│   └── voice/                     # end-to-end audio tests
├── scripts/
│   ├── setup_dev.sh
│   ├── download_models.sh
│   └── run_scenario_tests.py
├── docs/
│   ├── VOICE_AGENT_STACK_GUIDE.md
│   └── IMPLEMENTATION_PLAN.md     # this file
├── pyproject.toml                 # workspace root (uv or poetry)
├── Makefile
└── README.md
```

---

## 5. Technology Decisions (Locked)

Do not re-evaluate these during MVP unless a blocker is hit.

| Layer | Choice | Version |
|-------|--------|---------|
| Language | Python | 3.11+ |
| Package manager | **uv** (or Poetry) | latest |
| API framework | FastAPI | 0.110+ |
| Validation | Pydantic | v2 |
| ORM | SQLAlchemy 2.0 | async |
| Migrations | Alembic | latest |
| Task queue (later) | Redis | 7 |
| Voice framework | Pipecat | latest |
| STT | faster-whisper | large-v3 |
| TTS | Piper | latest |
| LLM | Qwen2.5-14B-Instruct AWQ | via vLLM |
| Dialogue | LangGraph | latest |
| Fuzzy match | rapidfuzz | latest |
| Telephony | Asterisk 20 | ARI |
| Containers | Docker Compose | MVP deploy |
| CI | GitHub Actions | — |
| Linting | ruff + mypy | strict on domain |

---

## 6. Implementation Phases

```
Phase 0 ──► Foundation & repo scaffold          (Week 1)
Phase 1 ──► Order Engine + 14 scenario tests    (Week 2–3)  ★ CRITICAL PATH
Phase 2 ──► Order API + persistence             (Week 3)
Phase 3 ──► LLM tools + dialogue manager        (Week 4)
Phase 4 ──► Voice pipeline (Pipecat)            (Week 4–5)
Phase 5 ──► Telephony (Asterisk)                (Week 5)
Phase 6 ──► Payment + SMS + post-order          (Week 5–6)
Phase 7 ──► Hardening + demo prep               (Week 6–8)
```

---

## 7. Sprint-by-Sprint Planner

### Sprint 0 — Foundation (Days 1–3)

**Goal:** Repo exists, dev environment runs, team aligned.

| # | Task | Owner | Output |
|---|------|-------|--------|
| 0.1 | Create GitHub repo, branch strategy (`main`, `develop`, feature branches) | Lead | repo live |
| 0.2 | Scaffold monorepo structure (Section 4) | Lead | folders + pyproject.toml |
| 0.3 | Set up `uv`/`poetry`, ruff, mypy, pre-commit hooks | Lead | `make lint` passes |
| 0.4 | Docker Compose: PostgreSQL + Redis | Backend | `docker compose up` works |
| 0.5 | Register Hugging Face, download model scripts stub | ML | `scripts/download_models.sh` |
| 0.6 | Request client menu matrix (Section 10) | PM/Lead | email sent |
| 0.7 | Import/adapt existing `order_engine` scaffold from README plan | Backend | `packages/order_engine/` |

**Exit criteria:** `make test` runs (even if zero tests). Docker stack healthy.

---

### Sprint 1 — Domain: Order Engine (Days 4–10)

**Goal:** All HOT BAGELS modifier logic passes unit tests without any LLM.

| # | Task | Owner | Output |
|---|------|-------|--------|
| 1.1 | Define domain models: `MenuItem`, `Modifier`, `Cart`, `LineItem` | Backend | `domain/*.py` |
| 1.2 | Menu catalog loader from `config/restaurants/*/menu.json` | Backend | `MenuCatalog` |
| 1.3 | Fuzzy item search with aliases + pronunciations (rapidfuzz) | Backend | `search_menu()` |
| 1.4 | Default modifier application (silent) | Backend | Test 2a passes |
| 1.5 | Required modifier detection → `ClarificationNeeded` | Backend | Test 2b passes |
| 1.6 | Multi-category ambiguity flag | Backend | Test 3 passes |
| 1.7 | Split line items (same item, different modifiers) | Backend | Test 4 passes |
| 1.8 | Modifier exclusion + max-selection rules | Backend | Test 5 passes |
| 1.9 | Business rules (24hr notice, item restrictions) | Backend | Test 8 passes |
| 1.10 | Special instructions per line item | Backend | Test 10 passes |
| 1.11 | Bundle / gift package support | Backend | Test 7 passes |
| 1.12 | `SpokenSummaryRenderer` + `SmsSummaryRenderer` (same data) | Backend | Test 13 foundation |
| 1.13 | Write all 14 scenarios in `tests/scenarios/` | Backend | pytest green |

**Exit criteria:** `pytest tests/scenarios/ -v` — 14/14 pass. No GPU. No LLM.

---

### Sprint 2 — Order API + Persistence (Days 11–15)

**Goal:** Order engine accessible via REST; orders persist across calls.

| # | Task | Owner | Output |
|---|------|-------|--------|
| 2.1 | FastAPI app scaffold with health check | Backend | `:8000/health` |
| 2.2 | Use case layer: `AddItem`, `RemoveItem`, `SetModifier`, `GetCart`, `Checkout` | Backend | `services/` |
| 2.3 | Tool endpoint: `POST /v1/calls/{call_id}/tool` | Backend | OpenAPI spec |
| 2.4 | Redis: active call session state | Backend | session per `call_id` |
| 2.5 | PostgreSQL: `orders`, `order_lines`, `restaurants` tables | Backend | Alembic migration |
| 2.6 | Order lookup by caller phone (post-order edit) | Backend | Test 14 foundation |
| 2.7 | Integration tests: API → domain → DB | Backend | `tests/integration/` |
| 2.8 | OpenAPI docs auto-generated | Backend | `/docs` |

**Exit criteria:** Scenarios 1–14 pass via HTTP calls (curl/httpx), not just direct Python.

---

### Sprint 3 — LLM + Dialogue (Days 16–22)

**Goal:** Text-based agent completes full order flow via tool calling.

| # | Task | Owner | Output |
|---|------|-------|--------|
| 3.1 | Spin up RunPod GPU pod, deploy vLLM + Qwen2.5-14B AWQ | ML | `:8001/v1/chat/completions` |
| 3.2 | Define tool schemas matching order-api endpoints | ML | `tools.json` |
| 3.3 | LangGraph state machine: GREETING → ORDERING → CONFIRMING → PAYMENT | ML | `packages/dialogue/` |
| 3.4 | Wire LLM tool calls → order-api HTTP | ML | text agent loop |
| 3.5 | Handle domain exceptions → spoken prompts | ML | clarification flow |
| 3.6 | System prompt templates per restaurant (`prompts.yaml`) | ML | config-driven |
| 3.7 | Text-mode test runner: 14 scenarios through LLM | ML | `scripts/run_scenario_tests.py` |
| 3.8 | Tune Qwen2.5; fall back to 7B if VRAM tight | ML | model config doc |

**Exit criteria:** Text chat agent passes 12+ of 14 scenarios. Failures logged with root cause.

---

### Sprint 4 — Voice Pipeline (Days 23–30)

**Goal:** Speak and hear — full voice order without phone line yet.

| # | Task | Owner | Output |
|---|------|-------|--------|
| 4.1 | Pipecat project scaffold in `apps/voice_agent/` | ML | pipeline starts |
| 4.2 | Integrate faster-whisper STT | ML | transcript → dialogue |
| 4.3 | Integrate Piper TTS | ML | response → audio |
| 4.4 | Silero VAD + end-of-turn detection | ML | natural pacing |
| 4.5 | Barge-in / interruption support | ML | checklist #6 |
| 4.6 | Connect dialogue manager from Sprint 3 | ML | same brain, voice I/O |
| 4.7 | WebRTC test client (LiveKit or Pipecat transport) | ML | browser test call |
| 4.8 | Latency profiling: target < 1.5s per turn | ML | metrics log |
| 4.9 | Pronunciation alias tuning (Test 11) | ML + Backend | menu config update |
| 4.10 | Voice end-to-end tests for top 5 scenarios | ML | `tests/voice/` |

**Exit criteria:** Complete order via browser voice call. Tests 1, 2, 4, 11 work by voice.

---

### Sprint 5 — Telephony (Days 31–35)

**Goal:** Real phone number answers and takes orders.

| # | Task | Owner | Output |
|---|------|-------|--------|
| 5.1 | Provision Hetzner VPS | DevOps | server IP |
| 5.2 | Install Asterisk 20 + PJSIP | DevOps | Asterisk running |
| 5.3 | Configure SIP trunk (Telnyx / client trunk) | DevOps | inbound calls work |
| 5.4 | ARI External Media → voice-agent WebSocket | ML | audio bridged |
| 5.5 | Caller ID passed to order-api (post-order lookup) | Backend | Test 14 |
| 5.6 | Human escalation: SIP transfer to client staff number | DevOps | checklist #13 |
| 5.7 | Store-closed + delivery-unavailable flows | Backend | checklist #12 |

**Exit criteria:** Call phone number → complete order by voice.

---

### Sprint 6 — Payment + SMS + Post-Order (Days 36–42)

**Goal:** Tests 12, 13, 14 pass on live calls.

| # | Task | Owner | Output |
|---|------|-------|--------|
| 6.1 | Payment service: isolated card capture (DTMF or spoken digits) | Backend | no LLM access |
| 6.2 | Mask card in all logs; Luhn validation | Backend | PCI hygiene |
| 6.3 | Mock processor for MVP (or client sandbox) | Backend | Test 12 |
| 6.4 | SMS gateway: render from `Cart.to_sms_summary()` | Backend | Test 13 |
| 6.5 | SMS sent on checkout confirmation | Backend | lifecycle message |
| 6.6 | Post-order modify: lookup + add item + re-confirm | Backend | Test 14 |
| 6.7 | Assert spoken == SMS == payment total (automated check) | Backend | parity test |

**Exit criteria:** Tests 12, 13, 14 pass on live phone call.

---

### Sprint 7 — Hardening & Demo (Days 43–56)

**Goal:** Client demo — all 14 tests pass 3× consistently.

| # | Task | Owner | Output |
|---|------|-------|--------|
| 7.1 | Run full 14-test suite × 3 repetitions | QA | test log spreadsheet |
| 7.2 | Fix all failures | All | green log |
| 7.3 | 5 concurrent call load test | DevOps | no crashes |
| 7.4 | Add 2nd dummy restaurant config (prove multi-tenant) | Backend | checklist #14 |
| 7.5 | Grafana dashboard: call duration, success rate, latency | DevOps | monitoring |
| 7.6 | Demo script document for client walkthrough | Lead | `docs/DEMO_SCRIPT.md` |
| 7.7 | Record backup demo video (insurance) | ML | video file |
| 7.8 | Code review + security pass on payment service | Lead | review notes |

**Exit criteria:** Client demo date set. 14/14 tests pass 3/3 runs.

---

## 8. Definition of Done per Phase

| Phase | Done when |
|-------|-----------|
| Phase 0 | Repo scaffolded, Docker up, lint passes |
| Phase 1 | `pytest tests/scenarios/` → 14/14 green, zero LLM |
| Phase 2 | Same 14 tests pass via HTTP API |
| Phase 3 | Text agent passes 12+/14 via LLM + tools |
| Phase 4 | Voice order completes in browser |
| Phase 5 | Voice order completes on real phone |
| Phase 6 | Tests 12, 13, 14 pass on phone |
| Phase 7 | 14/14 × 3 runs green, demo ready |

---

## 9. Environment Setup Checklist

### Local dev machine

```bash
# 1. Clone repo
git clone <repo-url> voice-multan && cd voice-multan

# 2. Install Python 3.11+
python --version  # must be 3.11+

# 3. Install uv (recommended)
pip install uv

# 4. Install dependencies
uv sync

# 5. Start infrastructure
docker compose -f infra/docker-compose.yml up -d

# 6. Run migrations
make migrate

# 7. Run tests
make test

# 8. (Later) Start GPU stack
docker compose -f infra/docker-compose.gpu.yml up -d
```

### Makefile targets (create in Sprint 0)

```makefile
lint:      ruff check . && mypy packages/
test:      pytest tests/ -v
test-scenarios: pytest tests/scenarios/ -v
migrate:   alembic upgrade head
dev-api:   uvicorn apps.order_api.main:app --reload
dev-voice: python apps/voice_agent/pipeline.py
```

---

## 10. Client Deliverables to Request (Week 1)

Send this list to the client **on Day 1**. Block Sprint 1 until items 1–3 are received.

| # | Deliverable | Why blocking |
|---|-------------|--------------|
| 1 | **Complete menu** — every item, price, category | Can't build engine |
| 2 | **Modifier matrix** — groups, defaults, required, exclusions per item | Tests 2, 4, 5 fail without this |
| 3 | **Business rules** — 24hr notice items, delivery zones, hours | Tests 8, 12 |
| 4 | **Pronunciation guide** — challah, bourekas, lox, etc. | Test 11 |
| 5 | **SMS provider** — existing webhook creds OR approval for GSM modem | Test 13 |
| 6 | **Payment processor** — sandbox API keys OR approval for mock | Test 12 |
| 7 | **Phone/SIP** — existing trunk details OR new number provisioned | Sprint 5 |
| 8 | **Human escalation number** — staff phone for transfer | Checklist #13 |
| 9 | **Sample successful human call recording** (optional) | Prompt tuning reference |

---

## 11. Coding Standards & Practices

### 11.1 Code style

- **ruff** for lint + format (line length 100)
- **mypy strict** on `packages/order_engine/` and `packages/dialogue/`
- Type hints on all public functions
- Google-style docstrings on domain services only

### 11.2 Naming conventions

| Thing | Convention | Example |
|-------|------------|---------|
| Files | snake_case | `add_item.py` |
| Classes | PascalCase | `CartLineItem` |
| Domain exceptions | PascalCase + Error suffix | `ClarificationNeededError` |
| API routes | kebab-case URLs | `/v1/calls/{id}/cart` |
| Config keys | snake_case JSON | `min_notice_hours` |
| Test files | `test_<scenario>.py` | `test_split_modifiers.py` |

### 11.3 Git workflow

```
main        ← production releases only
develop     ← integration branch
feature/*   ← one branch per task (e.g. feature/split-modifiers)
fix/*       ← bug fixes
```

- PR required for merge to `develop`
- CI must pass (lint + tests) before merge
- Squash merge preferred

### 11.4 Commit message format

```
feat(order-engine): add split modifier line item support
fix(voice): reduce STT latency on barge-in
test(scenarios): add HOT BAGELS test 4 split modifiers
docs: add implementation plan
```

### 11.5 Error handling pattern

```python
# Domain returns typed results — never raises for business rules
@dataclass
class AddItemResult:
    status: Literal["success", "clarification", "violation", "not_found"]
    message: str          # human-speakable prompt
    line_id: str | None
    options: list[str] | None  # for clarification
```

### 11.6 Logging

- Structured JSON logs (use `structlog`)
- Every call gets `call_id` (UUID) in all log lines
- Never log card numbers, CVV, or full phone numbers (mask: `+1***1234`)

---

## 12. Testing Strategy

### Test pyramid

```
                    ┌─────────┐
                    │  Voice  │  few — expensive, slow
                    │  E2E    │
                   ┌┴─────────┴┐
                   │ Integration│  API + DB + Redis
                  ┌┴───────────┴┐
                  │   Scenario  │  14 HOT BAGELS tests
                 ┌┴─────────────┴┐
                 │     Unit      │  domain logic — many, fast
                 └───────────────┘
```

| Layer | Location | Runs on | When |
|-------|----------|---------|------|
| Unit | `tests/unit/` | CPU, < 5s | Every commit |
| Scenario | `tests/scenarios/` | CPU, < 30s | Every PR |
| Integration | `tests/integration/` | Docker, < 2min | Every PR |
| Voice E2E | `tests/voice/` | GPU, < 10min | Nightly |

### The 14 scenario tests are the contract

File: `tests/scenarios/test_hot_bagels.py`

Each test:
1. Loads `hot_bagels_2nd_street` config
2. Feeds utterance(s) through use case layer
3. Asserts exact cart JSON structure
4. Asserts `spoken_summary == sms_summary`
5. Asserts no hallucinated items

---

## 13. Deployment & DevOps

### MVP environments

| Env | Purpose | Infrastructure |
|-----|---------|----------------|
| `local` | Dev | Docker Compose on laptop |
| `gpu-dev` | Voice testing | RunPod on-demand pod |
| `staging` | Pre-demo | Hetzner VPS + RunPod |
| `production` | Post-contract | Hetzner + RunPod Serverless |

### Docker Compose services (MVP)

```yaml
services:
  postgres:    # orders, config
  redis:       # call sessions
  order-api:   # FastAPI
  voice-agent: # Pipecat (GPU node)
  llm-server:  # vLLM (GPU node)
  asterisk:    # telephony (VPS)
```

### CI pipeline (GitHub Actions)

```yaml
on: [push, pull_request]
jobs:
  lint:   ruff + mypy
  test:   pytest tests/unit + tests/scenarios
  integration: pytest tests/integration (with postgres/redis services)
```

---

## 14. Risk Register & Blockers

| Risk | Probability | Impact | Mitigation | Owner |
|------|-------------|--------|------------|-------|
| Client delays menu data | High | Blocks Sprint 1 | Send request Day 1; use draft menu for scaffold | Lead |
| GPU cost overrun | Medium | Budget | RunPod on-demand; shutdown when not testing | ML |
| Qwen2.5 tool-calling failures | Medium | Tests 1, 6 fail | Tune prompts; try 14B; add fallback parsing | ML |
| ASR mishears food names | Medium | Test 11 fails | Pronunciation alias table + confirm-back | ML |
| No SIP trunk in time | Medium | No phone demo | WebRTC demo as backup; parallel SIP setup | DevOps |
| SMS not available | Low | Test 13 blocked | Mock SMS panel showing exact text | Backend |
| Payment PCI concerns | Low | Test 12 blocked | Mock vault; show architecture to client | Backend |
| Scope creep | High | Miss deadline | MVP scope locked (Section 10 of stack guide) | Lead |

---

## 15. Day 1 Kickoff — What to Do First

Execute in this exact order:

```
□ 1. Send client deliverables request (Section 10)
□ 2. Create GitHub repo + invite team
□ 3. Register: Docker Hub, Hugging Face
□ 4. Scaffold monorepo (Section 4 structure)
□ 5. Set up pyproject.toml, ruff, mypy, pre-commit
□ 6. docker compose up (postgres + redis)
□ 7. Create packages/order_engine/ with Cart + MenuItem stubs
□ 8. Write first scenario test: Test 2a (default modifiers)
□ 9. Implement until Test 2a passes
□ 10. Daily standup: scenario test count (target: 14/14 by end of Week 2)
```

### Week 1 success metric

> **14/14 scenario tests pass via pure Python domain code. Zero GPU spend.**

That is the single most important milestone. Everything else is wiring.

---

## Timeline Summary

| Week | Sprint | Milestone |
|------|--------|-----------|
| 1 | 0 + 1 | Repo + Order Engine + 14/14 unit tests |
| 2 | 1 + 2 | Order API + persistence |
| 3 | 3 | LLM text agent |
| 4 | 3 + 4 | Voice pipeline (browser) |
| 5 | 4 + 5 | Real phone + telephony |
| 6 | 6 | Payment + SMS + post-order |
| 7 | 7 | Hardening + 3× test runs |
| 8 | 7 | Demo prep + buffer |

**Total: 8 weeks · 2 developers · MVP demo-ready**

---

*Document version: 1.0*
*Companion doc: `VOICE_AGENT_STACK_GUIDE.md`*
*Next action: Execute Day 1 Kickoff checklist (Section 15)*
