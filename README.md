# Hot Bagels voice agent -- order engine starter

## What's here

- `menu_schema.json` -- the restaurant's menu as data: items, modifier
  groups, defaults, and which modifiers each item actually offers.
  Swap this file per client; nothing in `order_engine.py` is
  Hot-Bagels-specific (this is what checklist #14, reusability across
  restaurants, actually requires).
- `order_engine.py` -- the deterministic layer. The LLM never decides
  menu logic directly; it proposes an item + modifiers, and this code
  applies defaults, enforces required choices, rejects combinations
  the menu doesn't offer, and raises a clear "ask this question"
  signal when it genuinely can't guess.
- `test_harness.py` -- the 12 scenarios from the client's actual test
  document, run as text in / structured order out, no audio or model
  involved. Run it right now with zero GPU spend:

  ```
  cd hotbagels_voice_agent && python3 test_harness.py
  ```

  All 12 pass as of this scaffold. Treat this file as a living
  regression suite -- every time you add a menu item or a new edge
  case, add a test here before touching the voice pipeline. This is
  what the client's "a demo that works once does not constitute
  completion" line is actually asking for.

## Why it's split this way

Three checklist items only become true if you build it like this
rather than just prompting an LLM harder:

- "No hallucinated items, prices, or policies" -- guaranteed by a
  closed set of valid items/modifiers the code checks against, not by
  hoping the model behaves.
- "Final spoken order must exactly match the structured order used
  for payment, SMS, and fulfillment" -- guaranteed by `Order.summary()`
  being the single function that renders both the spoken confirmation
  and the SMS text, so there's no second code path where they could
  drift apart.
- Reusability across restaurants -- guaranteed by the menu living
  entirely in `menu_schema.json`, with zero Hot-Bagels-specific
  branches in the engine code.

## Cloud GPU plan, since you're renting

For development and running this test harness, you don't need a GPU
at all -- it's pure Python. You'll want one once you wire up the real
LLM, STT, and TTS together:

- **Development/testing**: an RTX 4090 (24GB) on Vast.ai or RunPod, on
  demand, currently runs roughly $0.30-0.50/hr depending on host. That's
  enough VRAM for a 4-bit-quantized 7B-14B model plus faster-whisper
  and Kokoro running at the same time. Only spin it up while you're
  actively testing the voice pipeline; shut it down between sessions.
- **If you need a bigger model** (32B-class, for stronger function-calling
  accuracy): an A100 80GB runs roughly $0.60-1.20/hr depending on
  spot vs on-demand. Worth trying once the small model's accuracy on
  your test cases plateaus, not before.
- **Eventual production**, once you've won the contract: look at
  RunPod Serverless or a similar scale-to-zero GPU endpoint, billed
  per second of actual compute. A restaurant phone line gets bursty,
  infrequent traffic, so paying for an idle 24/7 GPU is wasteful --
  serverless trades a small cold-start delay for not paying when the
  phone isn't ringing. You can always add one small always-on instance
  during peak hours later if cold starts prove noticeable.

## Next step: wiring this into the real pipeline

1. On your rented GPU, serve a model through vLLM with its
   OpenAI-compatible endpoint (e.g. Qwen2.5-7B/14B-Instruct or
   Llama-3.1-8B-Instruct, 4-bit quantized to fit comfortably).
2. Define one function-calling tool, `add_item(item_term,
   requested_modifiers, quantity, special_instructions)`, whose schema
   mirrors `process_add_item`'s signature in `order_engine.py`. The
   LLM's only job becomes filling in that tool call from speech; this
   file's `process_add_item` is what actually executes it.
3. Point Pipecat's LLM service at your vLLM endpoint instead of any
   hosted provider -- this is the step that makes the whole thing run
   with no AI API key, ever.
4. Catch `ClarificationNeeded`, `OrderRuleViolation`, and
   `AdvanceNoticeRequired` in the pipeline and turn each into the
   agent's next spoken line (their `.prompt` / message is already
   phrased as something sayable).
5. Once real speech is flowing through, re-run the same 12 scenarios
   end to end with actual audio, and add new ones for anything the
   live model gets wrong that the text-only harness didn't catch.
