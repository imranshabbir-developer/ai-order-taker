#!/usr/bin/env python3
"""Interactive text chat with the dialogue agent (Sprint 3)."""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dialogue.agent import DialogueAgent  # noqa: E402
from dialogue.llm import OpenAICompatibleLLM  # noqa: E402
from dialogue.order_client import OrderApiClient  # noqa: E402
from dialogue.prompts import load_prompts  # noqa: E402
from dialogue.settings import get_dialogue_settings  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description="Text chat with the dialogue agent")
    parser.add_argument(
        "--message",
        "-m",
        action="append",
        help="Send message(s) non-interactively and exit (smoke test)",
    )
    args = parser.parse_args()

    get_dialogue_settings.cache_clear()
    settings = get_dialogue_settings()
    restaurant_id = settings.default_restaurant_id
    call_id = f"chat-{uuid.uuid4().hex[:10]}"

    order_client = OrderApiClient(settings.order_api_base_url)
    try:
        health = await order_client.health()
        print(f"Order API: {settings.order_api_base_url} ({health.get('status', '?')})")
    except Exception as exc:
        print(f"Order API unreachable at {settings.order_api_base_url}: {exc}")
        print("Start the API first: python run_api.py")
        raise SystemExit(1) from exc

    llm = OpenAICompatibleLLM(
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout_seconds,
    )
    prompts = load_prompts(restaurant_id)
    agent = DialogueAgent(
        llm,
        order_client,
        prompts,
        restaurant_id,
        call_id,
        max_tool_rounds=settings.llm_max_tool_rounds,
    )

    start = await agent.start()
    print(f"\nAgent [{start.phase.value}]: {start.assistant_message}\n")

    if args.message:
        for user in args.message:
            print(f"You: {user}")
            turn = await agent.handle_user_message(user)
            print(f"\nAgent [{turn.phase.value}]: {turn.assistant_message}")
            if turn.tool_results:
                last = turn.tool_results[-1]
                print(f"  (engine: {last.status} — {last.message[:120]})")
            print()
        return

    print("Type your order (or 'quit').\n")

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break
        if not user:
            continue
        if user.lower() in {"quit", "exit", "q"}:
            print("Bye.")
            break

        try:
            turn = await agent.handle_user_message(user)
        except Exception as exc:
            print(f"\nError: {exc}\n")
            continue

        print(f"\nAgent [{turn.phase.value}]: {turn.assistant_message}")
        if turn.tool_results:
            last = turn.tool_results[-1]
            print(f"  (engine: {last.status} — {last.message[:120]})")
        print()
        if turn.done:
            print("Order complete.")
            break


if __name__ == "__main__":
    asyncio.run(main())
