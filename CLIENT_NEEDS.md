# What we need from you (client checklist)

Please send these **before Week 2** so menu data matches your real store.
Our draft menu in `config/restaurants/hot_bagels_2nd_street/menu.json` is built from your test document — we need your **official** data to replace it.

## Blocking (required for accurate MVP)

1. **Full menu export** — every item name, price, category
2. **Modifier matrix** — for each item:
   - Available modifiers
   - Default modifiers (applied silently)
   - Required choices (must ask if no default)
   - Exclusions (e.g. one milk type only, farina rules)
3. **Business rules** — e.g. Giant Pizza Bagel 24hr notice, any other restricted items
4. **Store hours** — per day, holidays
5. **Delivery zones & rules** — if delivery is in scope for demo

## Important for demo week

6. **Pronunciation list** — challah, bourekas/barakas, lox, etc.
7. **Human escalation phone number** — staff line for SIP transfer
8. **SMS** — existing provider webhook OR approval to use GSM modem for demo
9. **Payment** — sandbox credentials (Stripe/Square) OR approval for secure mock vault demo
10. **SIP / phone** — existing trunk details OR new inbound number for demo

## Optional but helpful

11. Sample recording of a successful human order call
12. Gift box / bundle instructions wording
13. Busy-period message text when kitchen is slammed

---

**Current status:** Order engine passes **13/13 automated scenarios** against draft menu data.
Once you send official menu JSON, we will update config and re-run tests.
