#!/usr/bin/env python3
"""Voice E2E — top Sprint 4 scenarios through VoiceOrderSession (direct/mock LLM)."""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dialogue.order_client import OrderApiClient  # noqa: E402
from dialogue.scenarios import SCENARIOS  # noqa: E402
from dialogue.settings import get_dialogue_settings  # noqa: E402

from apps.voice_agent.providers.tts import TextTTSProvider  # noqa: E402
from apps.voice_agent.session import VoiceOrderSession  # noqa: E402
from scripts.run_scenario_tests import _scripted_llm_for_scenario, _utterances  # noqa: E402

VOICE_SCENARIO_IDS = ["01", "02a", "04", "11", "13"]


async def run_voice_scenario(scenario: dict) -> tuple[bool, str]:
    restaurant_id = "hot_bagels_2nd_street"
    call_id = f"voice-e2e-{scenario['id']}-{uuid.uuid4().hex[:6]}"
    get_dialogue_settings.cache_clear()

    session = VoiceOrderSession(
        restaurant_id=restaurant_id,
        call_id=call_id,
        llm=_scripted_llm_for_scenario(scenario),
        tts=TextTTSProvider(),
        local_playback=False,
    )

    expected = str(scenario.get("expected_status", "success"))
    await session.start()
    last_status = ""
    for text in _utterances(scenario):
        turn = await session.process_text(text, speak=False)
        if turn.agent.tool_results:
            last_status = turn.agent.tool_results[-1].status

    ok = last_status == expected
    return ok, f"expected={expected} got={last_status or 'none'}"


async def main() -> int:
    try:
        client = OrderApiClient(get_dialogue_settings().order_api_base_url)
        await client.health()
    except Exception as exc:
        print(f"Order API not reachable: {exc}")
        return 1

    scenarios = [s for s in SCENARIOS if s["id"] in VOICE_SCENARIO_IDS]
    passed = 0
    for scenario in scenarios:
        ok, detail = await run_voice_scenario(scenario)
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {scenario['id']} {scenario['name']} — {detail}")
        if ok:
            passed += 1

    print(f"\n{passed}/{len(scenarios)} voice E2E scenarios passed")
    return 0 if passed == len(scenarios) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
