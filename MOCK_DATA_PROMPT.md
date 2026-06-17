# Mock Data Generator Prompt (ChatGPT / Gemini)

Copy everything inside the block below and paste it into ChatGPT or Gemini.
When it responds, save each JSON file into:
`restaurants-ai-agent/config/restaurants/hot_bagels_2nd_street/`

Then tell your developer: **"mock menu data is ready — continue Sprint 1"**

---

## COPY FROM HERE ↓

You are a restaurant data architect. Generate **realistic MOCK data** for a New York bagel shop called **"Hot Bagels 2nd Street"** to power an AI phone ordering agent. This is placeholder data for development only — it will be replaced with real client data later.

### Your output

Produce **4 separate valid JSON files** (no markdown, no commentary — JSON only in each code block, labeled by filename):

1. `menu.json`
2. `operations.json`
3. `integrations.json`
4. `pronunciations.json`

---

### CRITICAL: These 14 voice-order test scenarios MUST work with your data

Design menu rules so an order engine can pass all of these:

| # | Customer says | Expected behavior |
|---|---------------|-------------------|
| 1 | "Everything bagel, cream cheese, smoked lox, red onions, olives, scoop the dough" | One bagel + all modifiers attached |
| 2a | "Cream cheese sandwich and coffee milk no sugar" | Sandwich defaults applied silently; coffee gets milk + no sugar |
| 2b | "2 sourdough challahs" | MUST ask which variation (no default) |
| 3 | "Sandwich with eggs" | MUST list multiple egg sandwich types (sliced, scrambled, egg salad, sunny side up) |
| 4 | "Two Mediterranean Toasts — one no eggplant, one extra feta" | Two separate line items, different modifiers |
| 5 | "Coffee with red milk and blue milk" + "farina with coffee on side" | Reject two milks; reject coffee side with farina |
| 6 | "Breakfast for two" | Offer breakfast bundle OR suggest items |
| 7 | "Gift Box For 1-2 people AND write a gift card" | Bundle + gift note support |
| 8 | "Giant Pizza Bagel" | Refuse — requires 24hr notice, call store |
| 10 | "Tuna sandwich, smear tuna on both sides" | Special instructions field |
| 11 | "Two challahs, whole tray of barakas" | Fuzzy match challah + bourekas/barakas aliases |
| 12 | (payment) | N/A in menu — see integrations.json |
| 13 | (SMS parity) | N/A in menu — prices must be consistent |
| 14 | "Add Hash Browns 1/2 lb" to existing order | Item must exist in menu |

Include **at least 25 menu items** across categories: Bagels, Sandwiches, Egg Sandwiches, Toast, Bakery, Beverages, Breakfast, Sides, Specialty, Bundles.

Use **realistic NYC bagel shop prices** in cents (e.g. bagel $1.50–2.00, sandwich $7–12, coffee $3–4).

---

### FILE 1: menu.json — exact schema

```json
{
  "restaurant_id": "hot_bagels_2nd_street",
  "name": "Hot Bagels 2nd Street",
  "modifiers": [
    {
      "id": "snake_case_id",
      "name": "Display Name",
      "aliases": ["optional", "synonyms"],
      "price_cents": 0
    }
  ],
  "modifier_groups": [
    {
      "id": "group_id",
      "name": "Group Name",
      "min_selections": 0,
      "max_selections": 1,
      "default_modifier_ids": [],
      "modifier_ids": ["mod_id_1"]
    }
  ],
  "items": [
    {
      "id": "item_id",
      "name": "Item Name",
      "aliases": ["synonyms"],
      "category": "Category",
      "base_price_cents": 650,
      "modifier_group_ids": ["group_id"],
      "default_modifier_ids": ["mod_id"],
      "disallowed_modifier_ids": [],
      "restriction": null,
      "is_bundle": false
    }
  ],
  "bundles": [
    {
      "id": "bundle_id",
      "name": "Bundle Name",
      "aliases": ["synonyms"],
      "base_price_cents": 2499,
      "supports_gift_note": true
    }
  ],
  "cross_item_rules": [
    {
      "item_id": "farina",
      "disallowed_modifier_ids": ["coffee_on_side"],
      "message": "Human-readable rejection message"
    }
  ],
  "pronunciations": {},
  "hours": {}
}
```

**Rules for modifiers:**
- `default_modifier_ids` on item OR group = applied silently, do NOT ask customer
- `min_selections: 1` with empty defaults = MUST ask (e.g. challah variation)
- `max_selections: 1` on milk group = only one milk type allowed
- `restriction.min_notice_hours: 24` for special items like Giant Pizza Bagel
- `disallowed_modifier_ids` on item = hard block

**Required items (minimum):**
everything_bagel, cream_cheese_sandwich, coffee, sourdough_challah, sliced_egg_sandwich, scrambled_egg_sandwich, egg_salad_sandwich, sunny_side_up_egg_sandwich, mediterranean_toast, farina, tuna_sandwich, giant_pizza_bagel, hash_browns_half_lb, bourekas_tray, breakfast_for_two (bundle), gift_box_1_2 (bundle)

---

### FILE 2: operations.json

```json
{
  "restaurant_id": "hot_bagels_2nd_street",
  "store_hours": {
    "timezone": "America/New_York",
    "weekly": {
      "mon": { "open": "06:00", "close": "20:00" },
      "tue": { "open": "06:00", "close": "20:00" },
      "wed": { "open": "06:00", "close": "20:00" },
      "thu": { "open": "06:00", "close": "20:00" },
      "fri": { "open": "06:00", "close": "15:00" },
      "sat": { "closed": true },
      "sun": { "closed": true }
    },
    "closed_message": "We're closed right now. Our hours are Mon-Thu 6am-8pm, Fri 6am-3pm.",
    "busy_message": "We're experiencing high volume. Estimated wait is 25 minutes."
  },
  "delivery": {
    "enabled": true,
    "min_order_cents": 1500,
    "fee_cents": 399,
    "zones": [
      {
        "name": "Local",
        "zip_codes": ["10001", "10002", "10003"],
        "message": "Delivery available to your area."
      }
    ],
    "unavailable_message": "Delivery is not available to your address. Pickup is available."
  },
  "pickup": {
    "enabled": true,
    "estimated_minutes": 15
  },
  "escalation": {
    "staff_phone": "+1-555-010-0199",
    "triggers": ["customer_requested", "frustration", "unresolved_after_3_attempts"],
    "message": "Let me connect you with a team member."
  },
  "ordering_modes": ["pickup", "delivery", "scheduled_pickup", "scheduled_delivery"]
}
```

---

### FILE 3: integrations.json

```json
{
  "restaurant_id": "hot_bagels_2nd_street",
  "sms": {
    "mode": "mock",
    "provider": "mock_gateway",
    "from_number": "+1-555-010-0150",
    "templates": {
      "order_confirmation": "Hot Bagels: Your order is confirmed.\n{{order_summary}}\nTotal: {{total}}",
      "order_modified": "Hot Bagels: Your order was updated.\n{{order_summary}}",
      "order_cancelled": "Hot Bagels: Your order has been cancelled."
    },
    "notes": "MOCK — replace with client Twilio/webhook credentials later"
  },
  "payment": {
    "mode": "mock",
    "provider": "mock_vault",
    "accept_spoken_card": true,
    "never_repeat_full_card": true,
    "sandbox": {
      "test_card": "4111111111111111",
      "test_expiry": "12/28",
      "test_cvv": "123"
    },
    "notes": "MOCK — replace with Stripe/Square sandbox later"
  },
  "telephony": {
    "mode": "mock",
    "inbound_number": "+1-555-010-0100",
    "sip_trunk": null,
    "notes": "MOCK — replace with real SIP trunk for live demo"
  }
}
```

---

### FILE 4: pronunciations.json

Map ASR mishears to menu item IDs:

```json
{
  "restaurant_id": "hot_bagels_2nd_street",
  "aliases": {
    "sourdough_challah": ["challah", "chalah", "hallah", "halla"],
    "bourekas_tray": ["barakas", "bourekas", "borekas", "burekas"],
    "smoked_lox": ["lox", "locks", "lacks"],
    "everything_bagel": ["everything bagel", "every thing bagel"],
    "mediterranean_toast": ["med toast", "mediterranean"]
  }
}
```

---

### Quality rules

1. All IDs must be `snake_case`, unique, stable
2. All prices in **cents** (integer)
3. Every modifier referenced in groups/items must exist in `modifiers` array
4. Include 3+ bagel types, 4 egg sandwich types, 5+ beverages
5. Add 2–3 more items with `restriction.min_notice_hours` besides Giant Pizza Bagel
6. JSON must be valid — no trailing commas, no comments
7. Mark clearly in a top-level `"_mock": true` field in each file

After generating, list a **validation checklist** showing which of the 14 test scenarios each rule supports.

## COPY UNTIL HERE ↑
