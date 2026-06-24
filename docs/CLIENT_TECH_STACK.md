# Hot Bagels AI Voice Ordering — Technology Overview

**Document purpose:** Summary of the technologies, AI models, and libraries used in the implemented MVP. Intended for client review.

**Status:** Implemented and running in development/demo (Sprints 1–7). Payment and SMS use mock services suitable for testing; production gateways can be swapped in via configuration.

---

## 1. System overview

The solution is split into **three applications** that work together:

| Application | URL (local demo) | Role |
|-------------|------------------|------|
| **Voice client** | `http://127.0.0.1:8090` | Customer speaks or types an order; agent replies with voice |
| **Order API** | `http://127.0.0.1:8080` | Source of truth for menu, cart, pricing, checkout, orders, payments, SMS |
| **Admin dashboard** | `http://localhost:5173` | Staff view: orders list, cart inspector, menu, test scenarios, operations |

**Design principle:** The AI interprets natural language, but **all menu logic, prices, modifiers, and order state are enforced by deterministic code** (`order_engine`). This prevents hallucinated items or incorrect prices from reaching payment or fulfillment.

```
Customer (browser mic / text)
        │
        ▼
  Voice Server ──► STT (speech-to-text) ──► Dialogue Agent (LLM)
        │                    │                        │
        │                    │                        ▼
        │                    │              Order API + Order Engine
        │                    │              (cart, checkout, rules)
        ▼                    ▼
  TTS (text-to-speech) ◄── agent reply
        │
        ▼
  Admin dashboard ◄── same orders & carts via REST API
```

---

## 2. AI models (implemented)

Models are configured in `.env` and can use **cloud APIs** or **local Ollama** for the dialogue LLM.

| Layer | Model / service | Provider | Purpose |
|-------|-----------------|----------|---------|
| **Dialogue LLM** (scripts, batch tests) | `qwen2.5:7b` | **Ollama** (local) | Understands customer intent, calls order tools (add item, checkout, etc.) |
| **Voice LLM** (live browser demo) | `llama-3.1-8b-instant` | **Groq** (cloud) | Fast responses during live voice (~5–15 seconds per turn) |
| **Speech-to-text (STT)** | `whisper-large-v3` | **Groq** (cloud) | Converts microphone audio to text |
| **Text-to-speech (TTS)** | `en-US-JennyNeural` | **Microsoft Edge TTS** (via `edge-tts`) | Natural-sounding agent voice in the browser |

**Why two LLM setups?**
Local Ollama is cost-free and good for development and automated tests, but can be slow on CPU for live voice. Groq provides low-latency inference for the real-time voice experience.

**Alternative (supported in config, not required for demo):** Any **OpenAI-compatible** endpoint (e.g. vLLM on a GPU server) can replace Ollama/Groq by changing `LLM_BASE_URL` and `LLM_MODEL`.

---

## 3. Core frameworks

| Technology | Version (approx.) | Where used | Purpose |
|------------|-------------------|------------|---------|
| **Python** | 3.11+ | All backend services | Runtime for API, voice, dialogue, and order engine |
| **FastAPI** | 0.110+ | Order API, Voice server, Payment, SMS | REST and WebSocket APIs, request validation, OpenAPI docs |
| **Uvicorn** | 0.27+ | All FastAPI apps | ASGI web server |
| **React** | 18.3 | Admin dashboard | Interactive staff UI (orders, cart, scenarios) |
| **Vite** | 5.4 | Admin dashboard | Frontend build tool and dev server |
| **TypeScript** | 5.6 | Admin dashboard | Type-safe frontend code |

---

## 4. AI & dialogue libraries

| Library | Purpose in this project |
|---------|-------------------------|
| **LangGraph** | Manages dialogue **phases** (greeting → ordering → clarifying → confirming → payment → complete) |
| **LangChain Core** | Shared primitives used with LangGraph |
| **OpenAI Python SDK** | Client for chat completions and **tool/function calling** against Groq, Ollama, or vLLM (all OpenAI-compatible) |
| **edge-tts** | Generates MP3 audio for agent replies using Microsoft neural voices |
| **httpx** | HTTP calls to Groq Whisper STT, Order API, payment, and SMS services |

The dialogue agent exposes a fixed set of **tools** (e.g. `add_item`, `get_cart`, `checkout`). The LLM chooses tools; the **Order API executes them** and returns structured results.

---

## 5. Order engine & data libraries

| Library | Purpose |
|---------|---------|
| **Pydantic** | Validates menus, API requests/responses, and restaurant config |
| **RapidFuzz** | Fuzzy matching of spoken item names to menu entries (handles ASR typos and variants) |
| **PyYAML** | Loads per-restaurant agent prompts from `config/restaurants/*/prompts.yaml` |
| **python-dateutil** | Store hours and timezone-aware “today / tomorrow” order filters |

Restaurant data (menu, hours, prompts, pronunciations) lives in **`config/restaurants/`** as JSON/YAML — no code changes needed to update a menu for a new client.

---

## 6. Persistence & infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Primary database** | **PostgreSQL 16** | Orders, payments, SMS records, restaurant seed data |
| **ORM** | **SQLAlchemy 2** (async) + **asyncpg** | Async database access from Order API |
| **Migrations** | **Alembic** | Versioned schema updates (`alembic upgrade head`) |
| **Session cache** | **Redis 7** (optional) | Fast cache for active call carts during a phone/web session |
| **Containers** | **Docker Compose** | Local PostgreSQL and Redis (`infra/docker-compose.yml`) |

---

## 7. Supporting services (implemented)

| Service | Port (default) | Status | Purpose |
|---------|----------------|--------|---------|
| **Order API** | 8080 | Production-shaped | Cart, checkout, orders list, store hours, escalation |
| **Voice server** | 8090 | Demo-ready | WebSocket + browser UI for voice ordering |
| **Payment service** | configurable | **Mock** | Card capture isolated from LLM/voice logs; persists charges |
| **SMS gateway** | configurable | **Mock** | Sends order confirmation SMS text; records delivery status |
| **Admin dashboard** | 5173 | Demo-ready | Orders table (today/tomorrow), order detail, cart inspector |

Payment and SMS run as **separate microservices** so card numbers never pass through the AI or voice pipeline. For production, `PAYMENT_SERVICE_URL` and `SMS_GATEWAY_URL` can point to real processors (e.g. Stripe, Twilio).

---

## 8. Admin dashboard features (implemented)

- **Orders** — Filter by today, tomorrow, or last 30 days; click through to order detail (items, total, phone, payments, SMS).
- **Cart inspector** — Load a live voice session by Call ID (`?call=web-…`).
- **Menu** — Browse configured restaurant menu.
- **Test scenarios** — Run scripted ordering scenarios against the Order API.
- **Operations / Integrations** — View store hours and integration settings from config.

---

## 9. Voice client (implemented)

- Browser **WebSocket** connection to the voice server.
- **Microphone** capture with optional browser speech recognition; audio also sent to **Groq Whisper** for transcription.
- **Text input** fallback for testing without a mic.
- Links to admin dashboard for cart and order detail after checkout.

---

## 10. Quality assurance (implemented)

| Tool | Purpose |
|------|---------|
| **pytest** + **pytest-asyncio** | Unit and integration tests (menu rules, API, orders, payment, SMS) |
| **Ruff** | Python linting and formatting |
| **GitHub Actions CI** | Automated tests on push (PostgreSQL + Redis in CI) |

Includes **12+ scripted ordering scenarios** aligned with the client test document, plus voice scenario tests.

---

## 11. What is not in scope of this MVP

The following appear in longer-term plans but are **not** part of the current implemented stack:

- Live phone line / **Asterisk** telephony integration (skeleton docs only)
- Self-hosted **Whisper** or **Piper/Kokoro** on GPU (cloud Groq + Edge TTS used instead)
- Production payment processor (Stripe, etc.) — mock service only
- Production SMS provider (Twilio, etc.) — mock gateway only
- Hugging Face model downloads — not required for the current Groq/Ollama setup

---

## 12. Summary for stakeholders

| Concern | How the stack addresses it |
|---------|----------------------------|
| **Accurate menu & pricing** | Deterministic order engine; LLM only proposes actions via tools |
| **Voice experience** | Groq Whisper + Groq LLM + Edge TTS for responsive demo |
| **Staff workflow** | Admin dashboard with orders list, filters, and order detail |
| **Audit & fulfillment** | PostgreSQL stores orders, payments, and SMS |
| **Multi-restaurant** | Config-driven menus and prompts per restaurant folder |
| **Security (payments)** | Card data handled only by isolated payment service |

---

*Generated from the implemented codebase on branch `imran-dev`. For setup steps, see `README.md` and `docs/OLLAMA_SETUP.md`.*
