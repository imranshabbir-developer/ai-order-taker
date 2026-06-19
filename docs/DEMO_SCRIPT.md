# Client Demo Script — HOT BAGELS MVP

## Prerequisites

```bash
docker compose -f infra/docker-compose.yml up -d
pip install -r requirements-dev.txt
python run_api.py          # Order API
python run_voice_server.py # Voice browser client (optional)
```

Set `.env` with `LLM_API_KEY` (Groq) for live LLM voice/text demos.

## Demo flow (15 minutes)

### 1. Order engine (deterministic)

```bash
make test-scenarios
```

All 14 domain scenarios pass without LLM.

### 2. REST API

Open `http://127.0.0.1:8000/docs` and run:

- `POST .../tools/add_item` — everything bagel + modifiers
- `GET .../cart` — spoken_summary == sms_summary
- `POST .../checkout` — creates order, sends mock SMS
- `POST .../orders/{id}/payment` — mock card `4111111111111111`

### 3. Text agent (direct mode, no LLM)

```bash
make test-dialogue
```

### 4. Voice browser demo

1. Start Order API + `python run_voice_server.py`
2. Open `http://127.0.0.1:8090/`
3. Order: cream cheese sandwich + coffee no sugar
4. Confirm cart, checkout

### 5. Multi-restaurant proof

```bash
curl http://127.0.0.1:8000/v1/restaurants
```

Shows `hot_bagels_2nd_street` and `demo_cafe` (`_mock: true`).

## Test 12 — Payment

- Total always from `cart.total_cents`, never LLM
- Card sent only to payment service; logs show last 4 digits only
- Decline test card: `4000000000000002`

## Test 13 — SMS parity

Automated: `spoken_summary == sms_summary` on every tool response.

## Test 14 — Post-order modify

1. Checkout with customer phone
2. New call: `POST .../resume-from-phone`
3. `add_item` hash browns → updated total

## What requires client infra

| Item | Sprint |
|------|--------|
| Real SIP phone number | 5 |
| Production SMS provider | 6 |
| Stripe/Square sandbox | 6 |
| GPU vLLM (optional; Groq works for MVP) | 3 |
