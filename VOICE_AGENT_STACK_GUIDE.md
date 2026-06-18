# AI Voice Restaurant Agent — Open-Source Stack & MVP Guide

> **Purpose:** Win the HOT BAGELS MVP demo and position for the full production contract.
> **Constraint:** No paid APIs or API keys — fully self-hosted open-source stack.
> **Status:** Planning guide only — no implementation yet.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [What You Are Actually Building](#2-what-you-are-actually-building)
3. [Architecture Overview](#3-architecture-overview)
4. [Recommended Stack (Best for This MVP)](#4-recommended-stack-best-for-this-mvp)
5. [Component Deep Dive](#5-component-deep-dive)
6. [How Each Requirement Maps to the Stack](#6-how-each-requirement-maps-to-the-stack)
7. [HOT BAGELS Test Suite — Pass Strategy](#7-hot-bagels-test-suite--pass-strategy)
8. [Multi-Restaurant Config Model](#8-multi-restaurant-config-model)
9. [Hardware & Infrastructure](#9-hardware--infrastructure)
10. [MVP Scope vs Full Project Scope](#10-mvp-scope-vs-full-project-scope)
11. [Development Phases & Timeline](#11-development-phases--timeline)
12. [Team & Roles](#12-team--roles)
13. [Risks, Honest Limitations & Mitigations](#13-risks-honest-limitations--mitigations)
14. [What NOT to Do (Common MVP Killers)](#14-what-not-to-do-common-mvp-killers)
15. [Recommended Repo Structure (Future)](#15-recommended-repo-structure-future)
16. [Decision Summary — Copy This](#16-decision-summary--copy-this)

---

## 1. Executive Summary

This project is **not** “build a chatbot and add voice.” It is a **telephony + real-time voice pipeline + deterministic order engine + LLM for language only**.

The #1 reason MVPs fail here: treating the LLM as the source of truth for menu, prices, modifiers, and payments. **The LLM must never invent items.** All order truth lives in structured data validated by code.

### Recommended winning approach

| Layer | Choice | Why |
|-------|--------|-----|
| Telephony | **Asterisk** (self-hosted) or **LiveKit** (self-hosted WebRTC for demo) | Free, production-grade phone handling |
| Voice orchestration | **Pipecat** or **LiveKit Agents** | Open-source real-time voice agent pipelines |
| Speech-to-Text | **faster-whisper** (large-v3) | Best accuracy/speed ratio, runs locally |
| LLM | **Qwen2.5-14B-Instruct** (or 7B on limited GPU) | Strong tool-calling, JSON, instruction following |
| LLM runtime | **vLLM** or **Ollama** | Fast local inference |
| Text-to-Speech | **Piper TTS** (primary) + **Coqui XTTS** (fallback for quality) | Low latency, no cloud |
| Order brain | **Custom Python Order Engine** (Pydantic + rules) | Passes modifier/default/exclusion tests |
| Dialogue control | **LangGraph** state machine | Prevents loops, manages call flow |
| Database | **PostgreSQL** + **Redis** | Orders, sessions, restaurant config |
| SMS (self-hosted path) | **Kannel** + GSM modem **or** client-provided webhook | No Twilio API key |
| Payments | **Secure capture layer** + client PCI processor | LLM never touches card data |

### Realistic MVP timeline

| Team size | HOT BAGELS demo-ready | Full checklist production-ready |
|-----------|----------------------|----------------------------------|
| 1 senior full-stack dev | 10–14 weeks | 5–7 months |
| 2 devs (voice + backend) | **6–8 weeks** | 3–4 months |
| 3 devs (+ menu/config specialist) | **4–6 weeks** | 2.5–3 months |

**Recommended MVP target:** 6–8 weeks with 2 developers, phased delivery (see Section 11).

---

## 2. What You Are Actually Building

### The client's definition of "complete"

From the master checklist:

> *"The project is considered complete only when all behaviors are consistently demonstrated in live test calls and supporting customer communications. A demo that works once does not constitute completion."*

That means you need:

1. **Repeatable** live phone calls (not browser-only demos)
2. **Identical** data across voice, structured order, payment, and SMS
3. **Deterministic** menu/modifier behavior (tests 2, 4, 5, 8 will expose any LLM-only approach)
4. **Stateful** multi-turn conversations with interruption handling
5. **Multi-restaurant** configuration without code changes

### Core subsystems (5 pillars)

```
┌─────────────────────────────────────────────────────────────────┐
│  PILLAR 1: Telephony        — answer phone, audio stream I/O   │
│  PILLAR 2: Voice Pipeline   — STT → brain → TTS in real time   │
│  PILLAR 3: Order Engine     — menu, modifiers, cart, pricing   │
│  PILLAR 4: Dialogue Brain   — LLM + state machine + tools      │
│  PILLAR 5: Integrations     — SMS, payment, post-order lookup  │
└─────────────────────────────────────────────────────────────────┘
```

**Critical insight:** Pillars 3 and 4 must be separate. The LLM proposes actions; the Order Engine accepts or rejects them.

---

## 3. Architecture Overview

### High-level data flow

```
Phone Call (PSTN/SIP)
        │
        ▼
┌───────────────┐
│   Asterisk    │  ← answers call, streams audio
│   (Telephony) │
└───────┬───────┘
        │ PCM audio stream
        ▼
┌───────────────┐
│   Pipecat /   │  ← VAD, turn detection, barge-in
│ LiveKit Agent │
└───────┬───────┘
        │
   ┌────┴────┐
   ▼         ▼
┌──────┐  ┌──────────────────────────────────────┐
│ STT  │  │           Dialogue Orchestrator       │
│faster│  │  LangGraph state machine + Qwen2.5    │
│whisper│ │  Tools: add_item, set_modifier, etc.  │
└──┬───┘  └──────────────┬───────────────────────┘
   │                     │
   │              ┌──────▼──────┐
   │              │ Order Engine │ ← SOURCE OF TRUTH
   │              │ (Python)     │   menu JSON, rules,
   │              └──────┬───────┘   pricing, validation
   │                     │
   │              ┌──────▼──────┐
   └─────────────►│ Response    │
                  │ Generator   │
                  └──────┬──────┘
                         ▼
                  ┌──────────────┐
                  │  Piper TTS   │
                  └──────┬───────┘
                         ▼
                  Audio back to caller

Post-checkout:
  Order JSON → SMS gateway → Customer phone
  Order JSON → Payment vault → Processor (client-provided)
  Order JSON → PostgreSQL → Post-order lookup by caller ID
```

### The golden rule

```
SPOKEN OUTPUT = render(cart.to_spoken_summary())
SMS OUTPUT    = render(cart.to_sms_summary())
PAYMENT TOTAL = cart.total_cents

All three read from the SAME Cart object. Never let the LLM write the confirmation text freely.
```

---

## 4. Recommended Stack (Best for This MVP)

### 4.1 Primary stack (recommended)

| Category | Tool | License | Notes |
|----------|------|---------|-------|
| Language | **Python 3.11+** | PSF | Ecosystem for voice + ML |
| Telephony | **Asterisk 20** + **PJSIP** | GPL | Industry standard, free |
| Audio streaming | **Asterisk ARI** (External Media) | GPL | Stream audio to your Python app |
| Voice framework | **Pipecat** | BSD | Built for real-time voice agents |
| Alternative voice | **LiveKit** (self-hosted) | Apache 2.0 | Better if demo starts WebRTC-first |
| STT | **faster-whisper** | MIT | Use `large-v3` or `distil-large-v3` |
| VAD | **Silero VAD** | MIT | End-of-turn detection |
| LLM | **Qwen2.5-14B-Instruct** | Apache 2.0 | Best open tool-calling in class |
| LLM (low GPU) | **Qwen2.5-7B-Instruct** | Apache 2.0 | Minimum viable for MVP |
| LLM runtime | **vLLM** | Apache 2.0 | Production throughput |
| LLM runtime (dev) | **Ollama** | MIT | Easy local dev |
| TTS | **Piper** | MIT | ~50ms latency on CPU |
| TTS (quality) | **Coqui XTTS v2** | MPL | Better prosody, heavier |
| Orchestration | **LangGraph** | MIT | Call state machine |
| API layer | **FastAPI** | MIT | REST + WebSocket |
| Database | **PostgreSQL 16** | PostgreSQL | Orders, config |
| Cache/sessions | **Redis 7** | BSD | Active call state |
| Menu search | **rapidfuzz** + embeddings optional | MIT | Fuzzy item matching |
| Embeddings (optional) | **bge-small-en-v1.5** via **sentence-transformers** | MIT | Semantic menu match |
| Container | **Docker** + **docker-compose** | Apache 2.0 | Reproducible deploy |
| Monitoring | **Prometheus** + **Grafana** | Apache 2.0 | Call success metrics |

### 4.2 Alternative stacks (valid but lower priority)

| Instead of | Alternative | Trade-off |
|------------|-------------|-----------|
| Pipecat | **LiveKit Agents** | More infra setup, excellent scaling |
| faster-whisper | **whisper.cpp** | Faster on CPU, slightly less accurate |
| Qwen2.5 | **Llama 3.1 8B Instruct** | Weaker tool-calling for modifier logic |
| Qwen2.5 | **Mistral 7B v0.3** | Faster, less reliable on complex orders |
| Piper | **Kokoro TTS** | Newer, good quality, less mature |
| Asterisk | **FreeSWITCH** | Equivalent capability, different API |
| LangGraph | Raw Python state machine | Less maintainable at scale |

### 4.3 Models to avoid for this use case

| Model / Approach | Why avoid |
|------------------|-----------|
| Tiny LLMs (1–3B) | Fail multi-item modifier parsing consistently |
| Pure end-to-end speech LLM (no tools) | Cannot guarantee menu accuracy — fails test 5, 8, 13 |
| Relying on RAG alone for menu | Hallucination risk — fails checklist item 13 |
| OpenAI / Anthropic / ElevenLabs APIs | Violates your no-API-key requirement |
| Single prompt with full menu in context | Context overflow + inconsistency on long calls |

---

## 5. Component Deep Dive

### 5.1 Telephony — Asterisk (self-hosted, free)

**Why Asterisk:**
- Answers real PSTN phone calls (what the client will test on)
- No per-minute API fees
- Audio Streaming via ARI External Media → your Python voice agent

**Setup outline:**
1. Install Asterisk on a VPS or local server
2. Connect SIP trunk (client may provide) or use SIP-to-PSTN gateway
3. Route incoming calls to Stasis/ARI application
4. Stream bidirectional audio to Pipecat server

**For early development (before phone line ready):**
- Use **LiveKit** self-hosted with browser client simulating a phone call
- Same voice pipeline code — swap transport layer later

### 5.2 Voice Pipeline — Pipecat

**Pipecat** (https://github.com/pipecat-ai/pipecat) is an open-source framework for voice AI agents.

**What it handles:**
- Audio frame processing
- STT/TTS service integration
- Interruption (barge-in) when caller speaks over agent
- Pipeline composition

**Pipeline skeleton:**
```
transport.input() → vad → stt → user_context_aggregator
    → llm (with tools) → tts → transport.output()
```

**Key config for restaurant MVP:**
- `allow_interruptions=True` — required for checklist item 6
- End-of-turn: Silero VAD + 700ms silence threshold (tune per environment)
- Max response latency target: **< 1.5 seconds** per turn

### 5.3 Speech-to-Text — faster-whisper

**Model:** `Systran/faster-whisper-large-v3`

**Why:**
- Handles "challahs", "barakas", "lox" better than small models
- Runs on GPU with CTranslate2 (4–8x faster than original Whisper)
- Word-level timestamps for interruption handling

**Tuning for HOT BAGELS test 11 (pronunciation):**
- Maintain a **restaurant-specific vocabulary boost list** (custom post-processing fuzzy match)
- Example: ASR output "barakas" → fuzzy match menu item "bourekas" / "borekas"
- Do NOT rely on ASR alone — always fuzzy-match against menu catalog

```python
# Conceptual flow (not implementation)
asr_text = whisper.transcribe(audio)
candidates = fuzzy_match(asr_text, menu.all_item_names, threshold=75)
# Pass candidates to LLM as structured hints, not free text
```

### 5.4 LLM — Qwen2.5-Instruct (tool-calling mode)

**Why Qwen2.5 over alternatives:**

| Capability | Qwen2.5-14B | Llama 3.1 8B | Mistral 7B |
|------------|-------------|--------------|------------|
| Tool/function calling | Excellent | Good | Moderate |
| Multi-item parsing | Excellent | Good | Fair |
| JSON reliability | Excellent | Good | Fair |
| Follows "don't ask if default exists" | Good with system prompt + tools | Moderate | Moderate |
| VRAM (4-bit quant) | ~10 GB | ~6 GB | ~5 GB |

**How the LLM is used (narrow role):**

The LLM does **NOT**:
- Know prices
- Decide if a modifier is valid
- Generate final order confirmation text
- Handle payment data

The LLM **DOES**:
- Understand caller intent from transcript
- Call tools with structured parameters
- Ask clarification questions when tool returns `needs_clarification`
- Handle conversational filler ("actually", "wait", "remove that")

**Tool definitions (conceptual):**

```
search_menu(query)           → returns matching items/modifiers from engine
add_line_item(item_id, qty)  → returns line_id or error
set_modifier(line_id, mod_id) → returns success or validation error
remove_line_item(line_id)
set_special_instructions(line_id, text)
set_order_type(pickup|delivery|scheduled)
set_delivery_address(...)
get_cart_summary()           → engine generates spoken-ready summary
checkout()                   → triggers payment flow
cancel_order(order_id)
modify_order(order_id, ...)
escalate_to_human(reason)
```

Every tool call hits the **Order Engine** which validates against menu JSON.

### 5.5 Order Engine — Custom Python (most important component)

This is your competitive advantage. Build this right and you win the MVP.

**Data model:**

```
Restaurant
  ├── menu_categories[]
  ├── items[] (id, name, aliases[], base_price, category)
  ├── modifiers[] (id, name, group, required, default, exclusions[])
  ├── modifier_groups[] (min, max, rules)
  ├── bundles[] (gift box, breakfast for two)
  ├── business_rules[] (24hr notice, store hours, delivery zones)
  └── pronunciations[] (challah → aliases)

Cart
  ├── order_type (pickup|delivery|scheduled_*)
  ├── lines[] (line_id, item_id, qty, modifiers[], special_instructions)
  ├── delivery_info
  ├── scheduled_time
  └── customer_phone

Order (persisted)
  ├── cart snapshot
  ├── status (placed|modified|cancelled)
  ├── payment_status
  └── sms_sent_at
```

**Validation rules engine:**

| Rule type | Example | Test |
|-----------|---------|------|
| Default modifier | Cream cheese sandwich → plain CC, not toasted | Test 2a |
| Required modifier | Sourdough challah → must pick variation | Test 2b |
| Max selection | Coffee → one milk type only | Test 5 |
| Cross-item exclusion | Farina → coffee not allowed as side | Test 5 |
| Item restriction | Giant Pizza Bagel → 24hr notice | Test 8 |
| Split lines | Same item, different modifiers → separate line_ids | Test 4 |

**Implementation libraries:**
- **Pydantic v2** — schema validation
- **rapidfuzz** — fuzzy item name matching (test 1, 11)
- **python-dateutil** — scheduled order times
- **jsonschema** — restaurant config validation

### 5.6 Text-to-Speech — Piper (primary)

**Why Piper for MVP:**
- Runs on CPU (~real-time)
- Low latency critical for phone UX
- Multiple voices available

**Voice selection tip:** Pick a clear, neutral US English voice. Test with menu-heavy confirmations (long item lists).

**When to use Coqui XTTS instead:**
- Client feedback that Piper sounds too robotic
- Accept higher latency (~2–3x)

**Critical TTS rule:** Generate confirmation text from `cart.to_spoken_summary()` template — not from LLM free generation.

### 5.7 Dialogue State Machine — LangGraph

**States:**

```
GREETING → ORDERING → CLARIFYING → CONFIRMING → PAYMENT → COMPLETE
                ↑          │            │
                └──────────┴────────────┘ (corrections loop back)

Any state → ESCALATED (human handoff)
Any state → CLOSED_STORE / DELIVERY_UNAVAILABLE
```

**Why LangGraph:**
- Explicit state prevents infinite loops (checklist item 13)
- Easy to unit test each transition
- Survives long calls — state persisted in Redis per `call_id`

### 5.8 SMS — Self-hosted options (no Twilio API key)

| Option | Cost | MVP viability |
|--------|------|---------------|
| **Kannel** + USB GSM modem | Hardware ~$30 + SIM | Good for demo |
| Client's existing SMS provider webhook | Depends on client | Best for production |
| **Gammu** + GSM modem | Same as Kannel | Alternative |
| Email-to-SMS gateway | Free but unreliable | Demo only |

**SMS content:** Render from `cart.to_sms_summary()` — same function family as spoken summary.

**Test 13 pass condition:**
```
assert spoken_summary(cart) == sms_summary(cart)  # structurally identical
```

### 5.9 Payments — Spoken card (test 12)

**Non-negotiable security rules:**
- LLM never receives raw card number
- Agent never speaks full card number back
- Card capture via isolated **Payment Capture Service** (separate process)
- Digits captured via DTMF (keypad) preferred over spoken for PCI
- If spoken: use dedicated STT digit mode, mask immediately, tokenize

**Open-source components:**
- **Omnipay** (PHP) or direct processor SDK — client provides merchant account
- For MVP without processor: **mock vault** that validates Luhn algorithm + simulates success/fail
- Architecture must show real secure flow even if processor credentials come later

**What to demo:**
1. Caller confirms total (from order engine, not LLM)
2. Card captured securely
3. Success/fail message without repeating card
4. Order status updated in DB

---

## 6. How Each Requirement Maps to the Stack

### Master checklist → implementation mapping

| # | Requirement | Primary component | Secondary |
|---|-------------|-------------------|-----------|
| 1 | Ordering modes | Order Engine + LangGraph states | LLM tools |
| 2 | Fuzzy item recognition | rapidfuzz + menu aliases + LLM | faster-whisper |
| 3 | Modifiers & defaults | Order Engine rules | LLM proposes only |
| 4 | Multi-category resolution | Order Engine `search_menu()` returns ambiguity flag | LLM asks clarification |
| 5 | Order state management | Cart model in PostgreSQL/Redis | LangGraph |
| 6 | Conversational control | Pipecat barge-in + LangGraph loops | LLM |
| 7 | Confirmation accuracy | Template renderer from Cart | NOT LLM |
| 8 | Delivery & logistics | Order Engine + address validation | LLM collects slots |
| 9 | Payments | Payment Capture Service | Order Engine total |
| 10 | Post-order lifecycle | PostgreSQL order lookup by caller ID | LLM tools |
| 11 | SMS consistency | Shared cart renderer | Kannel/SMS gateway |
| 12 | Operational scenarios | Business rules in restaurant config | LangGraph branches |
| 13 | Stability & reliability | Order Engine validation + state machine | Monitoring |
| 14 | Multi-restaurant | JSON/YAML config per restaurant | No hard-coded menu |

---

## 7. HOT BAGELS Test Suite — Pass Strategy

| Test | Utterance | Pass mechanism |
|------|-----------|----------------|
| **1** | Everything bagel + modifiers + scoop the dough | Fuzzy match "everything bagel" → item; modifiers attached via tools; "scoop the dough" → special_instructions or modifier ID |
| **2a** | Cream cheese sandwich + coffee milk no sugar | Engine applies sandwich defaults silently; coffee gets milk modifier + sugar=no override |
| **2b** | 2 sourdough challahs | Engine returns `needs_clarification: [variant_list]` → LLM asks which variation |
| **3** | Sandwich with eggs | `search_menu("eggs sandwich")` returns multiple matches → LLM lists options |
| **4** | Two Mediterranean Toasts, different mods | Two `add_line_item` calls with different `line_id`s and modifier sets |
| **5** | Red milk + blue milk; farina + coffee side | Engine rejects second milk; engine rejects farina+coffee combo |
| **6** | Breakfast for two | Search bundles → if exists list; else LLM suggests items via `search_menu` |
| **7** | Gift box + gift card note | Bundle item + `special_instructions` on order or line |
| **8** | Giant Pizza Bagel | Business rule triggers: "requires 24hr notice, please call store" |
| **10** | Tuna sandwich, smear both sides | special_instructions field, confirmed in summary |
| **11** | Challahs, barakas | ASR + fuzzy alias table in menu config |
| **12** | Spoken card payment | Payment Capture Service; total from cart |
| **13** | SMS consistency | Single renderer — structural equality check |
| **14** | Modify recent order | Lookup by caller ID → `modify_order` tool → re-confirm |

### Pre-demo test script

Run all 14 tests **3 times each** on different days. Client said one success is not completion.

---

## 8. Multi-Restaurant Config Model

Each restaurant is a config bundle — no code changes to onboard a new client.

```
restaurants/
  hot_bagels_2nd_street/
    menu.json
    modifiers.json
    rules.json
    hours.json
    delivery_zones.json
    pronunciations.json
    prompts.yaml          # LLM system prompt templates only
```

**`rules.json` example concepts:**

```json
{
  "item_restrictions": {
    "giant_pizza_bagel": {
      "min_notice_hours": 24,
      "action": "refuse_and_advise_call_store"
    }
  },
  "modifier_exclusions": {
    "farina": {
      "disallowed_modifiers": ["coffee_on_side"]
    }
  },
  "modifier_groups": {
    "coffee_milk": { "min": 0, "max": 1, "default": "whole_milk" }
  }
}
```

---

## 9. Hardware & Infrastructure

### Minimum hardware (development)

| Component | Spec | Notes |
|-----------|------|-------|
| GPU | **NVIDIA RTX 4090 24GB** or **A6000** | Runs Qwen2.5-14B 4-bit + faster-whisper simultaneously |
| GPU (budget) | **RTX 3090 24GB** or **RTX 4080 16GB** | Use Qwen2.5-7B instead of 14B |
| CPU | 8+ cores | Piper TTS on CPU |
| RAM | 32 GB minimum | 64 GB recommended |
| Storage | 500 GB NVMe | Models ~20–40 GB total |

### Production MVP server (single box)

| Service | Resource |
|---------|----------|
| vLLM (Qwen2.5-14B AWQ) | GPU 10–12 GB VRAM |
| faster-whisper large-v3 | GPU 2–3 GB VRAM (or CPU fallback) |
| Piper TTS | CPU ~1 core |
| Asterisk | CPU ~1 core |
| PostgreSQL + Redis | 4 GB RAM |
| Pipecat agent | 2 GB RAM |

### Cloud without API keys

Self-host on:
- **Hetzner** GPU servers (cheapest bare-metal GPU rental — you pay for hardware, not AI API)
- **Vultr** GPU instances
- Client's own hardware on-premise

No OpenAI/Anthropic/ElevenLabs/Twilio bills.

---

## 10. MVP Scope vs Full Project Scope

### MVP (win the contract) — must pass

Priority P0 — all HOT BAGELS tests + core checklist:

- [x] Pickup ordering (delivery can be P1 if time-constrained)
- [x] Full modifier/default/exclusion logic
- [x] Split modifier lines
- [x] Fuzzy menu matching + pronunciation aliases
- [x] Business rules (24hr notice)
- [x] Special instructions
- [x] Single final confirmation (spoken = structured)
- [x] Spoken payment flow (secure)
- [x] SMS matching spoken order
- [x] Post-order modification on callback
- [x] Human escalation path
- [x] Store closed handling

Priority P1 — show architecture ready, demo if time:

- [ ] Scheduled pickup/delivery
- [ ] Full delivery address flow
- [ ] Switch order type mid-call
- [ ] Multi-restaurant config (show 2nd dummy restaurant)

Priority P2 — full contract scope:

- [ ] All 4 ordering modes polished
- [ ] High-volume/busy period messaging
- [ ] Full cancellation flows
- [ ] Production PCI certification
- [ ] Multi-location client dashboard

---

## 11. Development Phases & Timeline

### Phase 0 — Setup & menu digitization (Week 1)

| Task | Days | Output |
|------|------|--------|
| Obtain HOT BAGELS full menu + modifier matrix from client | 1–2 | menu.json draft |
| Set up dev environment (Docker, GPU, Ollama/vLLM) | 1 | dev stack running |
| Asterisk or LiveKit local telephony test | 1–2 | "hello world" call |
| Digitize menu with all modifiers, defaults, exclusions | 2–3 | validated menu.json |

**Milestone:** Call a number, hear Piper TTS greeting.

---

### Phase 1 — Order Engine (Week 2–3) ⭐ Most critical

| Task | Days | Output |
|------|------|--------|
| Cart data model (Pydantic) | 1 | cart.py |
| Menu loader + validation | 1 | config loader |
| Fuzzy item search (rapidfuzz) | 1 | search_menu() |
| Modifier validation (defaults, required, exclusions) | 2–3 | rules engine |
| Split line item support | 1 | line_id architecture |
| Unit tests for tests 2, 4, 5, 8 | 2 | pytest suite |
| Spoken + SMS summary renderer | 1 | template engine |

**Milestone:** Pass tests 2, 4, 5, 8 via API (no voice yet).

---

### Phase 2 — LLM tool integration (Week 3–4)

| Task | Days | Output |
|------|------|--------|
| Define tool schemas | 1 | tools.json |
| LangGraph state machine | 2 | dialogue states |
| Qwen2.5 + vLLM tool calling wired to Order Engine | 2 | working text agent |
| Test tests 1, 3, 6, 7, 10 via text chat | 2 | text-based pass |
| Prompt engineering + guardrails | 1 | system prompts |

**Milestone:** Full order flow works in text chat (terminal), all modifier logic correct.

---

### Phase 3 — Voice pipeline (Week 4–5)

| Task | Days | Output |
|------|------|--------|
| Pipecat + faster-whisper integration | 2 | STT working |
| Piper TTS integration | 1 | TTS working |
| Barge-in / interruption handling | 1 | conversational control |
| End-to-end voice → tools → voice | 2 | voice agent MVP |
| Pronunciation alias tuning (test 11) | 1 | menu aliases |
| Latency optimization | 1 | < 1.5s per turn |

**Milestone:** Complete order over phone by voice.

---

### Phase 4 — Payment, SMS, post-order (Week 5–6)

| Task | Days | Output |
|------|------|--------|
| Payment Capture Service (secure) | 2 | test 12 pass |
| SMS gateway integration | 1–2 | test 13 pass |
| Order persistence + caller ID lookup | 1 | test 14 pass |
| Post-order modify flow | 1 | callback edit works |
| Human escalation (SIP transfer or callback queue) | 1 | escalation path |

**Milestone:** Tests 12, 13, 14 pass on live calls.

---

### Phase 5 — Hardening & demo prep (Week 6–8)

| Task | Days | Output |
|------|------|--------|
| Run all 14 tests × 3 repetitions | 2 | test log |
| Fix edge cases and loops | 2 | stability |
| Store closed / busy period flows | 1 | ops scenarios |
| Multi-restaurant config demo | 1 | 2nd restaurant |
| Load test (5 concurrent calls) | 1 | performance report |
| Demo script + client walkthrough doc | 1 | demo kit |

**Milestone:** Client demo — all 14 tests pass consistently.

---

### Timeline summary

```
Week 1   ████░░░░░░  Setup + menu digitization
Week 2   ████████░░  Order Engine core
Week 3   ████████░░  Order Engine + LLM tools
Week 4   ██████░░░░  Voice pipeline
Week 5   ████████░░  Payment + SMS + post-order
Week 6   ██████░░░░  Integration hardening
Week 7   ████████░░  Test repetition + fixes
Week 8   ██████░░░░  Demo prep + buffer
```

**Total: 6–8 weeks** (2 developers, working in parallel on Order Engine + Voice Pipeline from Week 2).

---

## 12. Team & Roles

| Role | Responsibility | Phase |
|------|----------------|-------|
| **Backend / Order Engine dev** | Menu, cart, rules, SMS, payment, DB | 1, 4, 5 |
| **Voice / ML dev** | Pipecat, STT, TTS, LLM, latency | 0, 3, 5 |
| **Menu config specialist** (part-time) | Digitize HOT BAGELS menu accurately | 0, 1 |
| **QA / client liaison** (part-time) | Run 14 tests, log failures | 5 |

Minimum viable team: **2 developers**.
Ideal for 6-week delivery: **2 devs + 1 menu specialist**.

---

## 13. Risks, Honest Limitations & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Incomplete menu data from client | Engine can't validate — fails tests 2, 5, 8 | Request full modifier matrix Week 1; block Phase 1 until received |
| GPU hardware unavailable | Can't run 14B model locally | Use Qwen2.5-7B on CPU with Ollama (slower but works for demo) |
| SMS without paid gateway | Can't send real texts | GSM modem + Kannel; or ask client for their existing SMS webhook |
| PCI payment compliance | Legal exposure | Isolate capture service; client provides certified processor; never store raw CVV |
| ASR mishears cultural food names | Test 11 fails | Pronunciation alias table + confirm-back strategy |
| LLM loops or hallucinates | Test 13 fails, client trust lost | Order Engine rejects invalid tools; template-rendered confirmations |
| Latency > 3 seconds | Client perceives as broken | Piper on CPU; vLLM AWQ quant; stream TTS early |
| "No API key" interpreted too strictly | No phone number at all | SIP trunk is telecom service (not AI API) — clarify with client |

---

## 14. What NOT to Do (Common MVP Killers)

1. **Don't put the full menu in the LLM prompt** — use tool calls to search menu
2. **Don't let the LLM generate prices or totals** — always compute in Order Engine
3. **Don't let the LLM write the final confirmation** — template from cart object
4. **Don't skip unit tests on the Order Engine** — voice hides bugs until live demo
5. **Don't demo in browser only** — client will call a phone number
6. **Don't use a single LLM call per turn** — use tools + validation loop
7. **Don't hard-code HOT BAGELS items in Python** — use config JSON
8. **Don't defer test 13 (SMS parity)** — it catches the most embarrassing failures
9. **Don't train/fine-tune a custom LLM for MVP** — unnecessary; tool-calling + good menu data wins
10. **Don't aim for perfect voice quality first** — aim for perfect order accuracy first

---

## 15. Recommended Repo Structure (Future)

```
voice-multan/
├── apps/
│   ├── telephony/          # Asterisk configs, ARI app
│   ├── voice_agent/        # Pipecat pipeline
│   ├── order_engine/       # Cart, menu, rules (THE BRAIN)
│   ├── payment_service/    # Secure card capture
│   └── sms_gateway/        # Kannel integration
├── config/
│   └── restaurants/
│       └── hot_bagels_2nd_street/
├── tests/
│   ├── unit/               # Order engine tests (tests 2,4,5,8)
│   ├── integration/        # LLM tool tests
│   └── voice/              # End-to-end call tests
├── scripts/
│   └── run_test_suite.py   # Automated 14-test runner
├── docker-compose.yml
└── docs/
    └── VOICE_AGENT_STACK_GUIDE.md  ← this file
```

---

## 16. Decision Summary — Copy This

If you need to make fast decisions, use this:

```
Telephony:     Asterisk (production) + LiveKit (dev fallback)
Voice frame:   Pipecat
STT:           faster-whisper large-v3
TTS:           Piper (speed) / Coqui XTTS (quality fallback)
LLM:           Qwen2.5-14B-Instruct via vLLM
Orchestration: LangGraph
Order logic:   Custom Python Order Engine (Pydantic + rapidfuzz)
Database:      PostgreSQL + Redis
SMS:           Kannel + GSM modem (or client webhook)
Payments:      Isolated capture service + client processor
Timeline:      6–8 weeks, 2 developers
First build:   Order Engine (Week 2) — NOT the voice pipeline
Win condition: All 14 HOT BAGELS tests pass 3× in live phone calls
Golden rule:   spoken == SMS == payment total == cart JSON
```

---

## Next Steps (When You Are Ready to Implement)

1. Confirm with client: full menu + modifier matrix + business rules document
2. Confirm telephony: will they provide SIP trunk / phone number?
3. Confirm SMS: their existing provider or self-hosted GSM acceptable?
4. Confirm payment: which processor / mock acceptable for MVP?
5. Start Phase 0: menu digitization + dev environment setup

---

*Document version: 1.0 — Planning guide for voice-multan MVP*
*Requirements source: AI Voice Restaurant Acceptance Checklist + HOT BAGELS Critical Order Tests*
