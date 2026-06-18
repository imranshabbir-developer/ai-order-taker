#!/usr/bin/env python3
"""Run HOT BAGELS scenarios through the dialogue stack.

Modes:
  direct (default) — scripted tool calls via Order API (no LLM, CI-safe)
  llm              — full LLM agent (requires vLLM/Ollama at LLM_BASE_URL)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dialogue.agent import DialogueAgent  # noqa: E402
from dialogue.llm import LLMCompletion, LLMMessage, MockLLM, OpenAICompatibleLLM  # noqa: E402
from dialogue.order_client import OrderApiClient  # noqa: E402
from dialogue.prompts import load_prompts  # noqa: E402
from dialogue.scenarios import SCENARIOS  # noqa: E402
from dialogue.settings import get_dialogue_settings  # noqa: E402


def _utterances(scenario: dict) -> list[str]:
    if "utterances" in scenario:
        return [str(u) for u in scenario["utterances"]]
    return [str(scenario.get("utterance", ""))]


def _scripted_llm_for_scenario(scenario: dict) -> MockLLM:
    """Build tool-call script that mirrors deterministic scenario expectations."""
    steps: list[LLMCompletion] = []
    sid = str(scenario["id"])
    utterances = _utterances(scenario)

    if sid == "01":
        steps.append(
            LLMCompletion(
                message=LLMMessage(
                    role="assistant",
                    content=None,
                    tool_calls=[
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "add_item",
                                "arguments": json.dumps(
                                    {
                                        "item_term": "everything bagel",
                                        "requested_modifiers": [
                                            "cream cheese",
                                            "smoked lox",
                                            "red onions",
                                            "olives",
                                        ],
                                        "special_instructions": "scoop the dough",
                                    }
                                ),
                            },
                        }
                    ],
                )
            )
        )
    elif sid == "02a":
        steps.extend(
            [
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "add_item",
                                    "arguments": json.dumps({"item_term": "cream cheese sandwich"}),
                                },
                            }
                        ],
                    )
                ),
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": "c2",
                                "type": "function",
                                "function": {
                                    "name": "add_item",
                                    "arguments": json.dumps(
                                        {
                                            "item_term": "coffee",
                                            "requested_modifiers": ["milk", "no sugar"],
                                        }
                                    ),
                                },
                            }
                        ],
                    )
                ),
            ]
        )
    elif sid == "02b":
        steps.append(
            LLMCompletion(
                message=LLMMessage(
                    role="assistant",
                    tool_calls=[
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "add_item",
                                "arguments": json.dumps(
                                    {"item_term": "sourdough challah", "quantity": 2}
                                ),
                            },
                        }
                    ],
                )
            )
        )
    elif sid == "03":
        steps.append(
            LLMCompletion(
                message=LLMMessage(
                    role="assistant",
                    tool_calls=[
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "check_ambiguity",
                                "arguments": json.dumps({"query": "sandwich with eggs"}),
                            },
                        }
                    ],
                )
            )
        )
    elif sid == "04":
        steps.extend(
            [
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "add_item",
                                    "arguments": json.dumps(
                                        {
                                            "item_term": "mediterranean toast",
                                            "requested_modifiers": ["no eggplant"],
                                        }
                                    ),
                                },
                            }
                        ],
                    )
                ),
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": "c2",
                                "type": "function",
                                "function": {
                                    "name": "add_item",
                                    "arguments": json.dumps(
                                        {
                                            "item_term": "mediterranean toast",
                                            "requested_modifiers": ["extra feta"],
                                        }
                                    ),
                                },
                            }
                        ],
                    )
                ),
            ]
        )
    elif sid == "05":
        steps.append(
            LLMCompletion(
                message=LLMMessage(
                    role="assistant",
                    tool_calls=[
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "add_item",
                                "arguments": json.dumps(
                                    {
                                        "item_term": "coffee",
                                        "requested_modifiers": ["red milk", "blue milk"],
                                    }
                                ),
                            },
                        }
                    ],
                )
            )
        )
    elif sid == "06":
        steps.append(
            LLMCompletion(
                message=LLMMessage(
                    role="assistant",
                    tool_calls=[
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "add_item",
                                "arguments": json.dumps({"item_term": "breakfast for two"}),
                            },
                        }
                    ],
                )
            )
        )
    elif sid == "07":
        steps.append(
            LLMCompletion(
                message=LLMMessage(
                    role="assistant",
                    tool_calls=[
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "add_item",
                                "arguments": json.dumps(
                                    {
                                        "item_term": "gift box for 1-2 people",
                                        "special_instructions": "Happy Birthday!",
                                    }
                                ),
                            },
                        }
                    ],
                )
            )
        )
    elif sid == "08":
        steps.append(
            LLMCompletion(
                message=LLMMessage(
                    role="assistant",
                    tool_calls=[
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "add_item",
                                "arguments": json.dumps({"item_term": "giant pizza bagel"}),
                            },
                        }
                    ],
                )
            )
        )
    elif sid == "10":
        steps.append(
            LLMCompletion(
                message=LLMMessage(
                    role="assistant",
                    tool_calls=[
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {
                                "name": "add_item",
                                "arguments": json.dumps(
                                    {
                                        "item_term": "tuna sandwich",
                                        "special_instructions": "Smear tuna on both sides",
                                    }
                                ),
                            },
                        }
                    ],
                )
            )
        )
    elif sid == "11":
        steps.extend(
            [
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "add_item",
                                    "arguments": json.dumps(
                                        {
                                            "item_id": "sourdough_challah",
                                            "requested_modifiers": ["braided"],
                                            "quantity": 2,
                                        }
                                    ),
                                },
                            }
                        ],
                    )
                ),
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": "c2",
                                "type": "function",
                                "function": {
                                    "name": "add_item",
                                    "arguments": json.dumps({"item_term": "barakas"}),
                                },
                            }
                        ],
                    )
                ),
            ]
        )
    elif sid == "13":
        steps.extend(
            [
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "add_item",
                                    "arguments": json.dumps({"item_term": "cream cheese sandwich"}),
                                },
                            }
                        ],
                    )
                ),
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": "c2",
                                "type": "function",
                                "function": {
                                    "name": "add_item",
                                    "arguments": json.dumps(
                                        {
                                            "item_term": "coffee",
                                            "requested_modifiers": ["no sugar"],
                                        }
                                    ),
                                },
                            }
                        ],
                    )
                ),
            ]
        )
    elif sid == "14":
        steps.extend(
            [
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "add_item",
                                    "arguments": json.dumps({"item_term": "cream cheese sandwich"}),
                                },
                            }
                        ],
                    )
                ),
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": "c2",
                                "type": "function",
                                "function": {
                                    "name": "add_item",
                                    "arguments": json.dumps({"item_term": "hash browns half lb"}),
                                },
                            }
                        ],
                    )
                ),
            ]
        )
    else:
        for i, text in enumerate(utterances):
            steps.append(
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        tool_calls=[
                            {
                                "id": f"c{i}",
                                "type": "function",
                                "function": {
                                    "name": "add_item",
                                    "arguments": json.dumps({"item_term": text}),
                                },
                            }
                        ],
                    )
                )
            )

    steps.append(
        LLMCompletion(
            message=LLMMessage(role="assistant", content="Got it."),
            finish_reason="stop",
        )
    )
    return MockLLM(steps)


async def run_scenario(
    agent: DialogueAgent,
    scenario: dict,
    *,
    use_graph: bool = False,
) -> tuple[bool, str]:
    from dialogue.graph import build_dialogue_graph

    expected = str(scenario.get("expected_status", "success"))
    utterances = _utterances(scenario)
    last_status = ""

    if use_graph:
        await agent.reset()
        graph = build_dialogue_graph(agent)
        for text in utterances:
            state = await graph.ainvoke(
                {
                    "restaurant_id": agent.restaurant_id,
                    "call_id": agent.call_id,
                    "user_message": text,
                    "phase": agent.phase.value,
                }
            )
            last_status = str(state.get("last_status") or last_status)
    else:
        await agent.start()
        for text in utterances:
            turn = await agent.handle_user_message(text)
            if turn.tool_results:
                last_status = turn.tool_results[-1].status

    ok = last_status == expected
    detail = f"expected={expected} got={last_status or 'none'}"
    return ok, detail


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run dialogue scenario tests")
    parser.add_argument(
        "--mode",
        choices=("direct", "llm"),
        default="direct",
        help="direct=MockLLM tool scripts; llm=real OpenAI-compatible endpoint",
    )
    parser.add_argument("--graph", action="store_true", help="Route turns through LangGraph")
    parser.add_argument("--id", dest="scenario_id", help="Run a single scenario id")
    args = parser.parse_args()

    get_dialogue_settings.cache_clear()
    settings = get_dialogue_settings()
    restaurant_id = settings.default_restaurant_id
    order_client = OrderApiClient(settings.order_api_base_url)

    try:
        await order_client.health()
    except Exception as exc:
        print(f"Order API not reachable: {exc}")
        return 1

    prompts = load_prompts(restaurant_id)
    scenarios = SCENARIOS
    if args.scenario_id:
        scenarios = [s for s in SCENARIOS if s["id"] == args.scenario_id]
        if not scenarios:
            print(f"Unknown scenario id: {args.scenario_id}")
            return 1

    passed = 0
    for scenario in scenarios:
        try:
            call_id = f"scenario-{scenario['id']}-{uuid.uuid4().hex[:6]}"
            if args.mode == "llm":
                llm = OpenAICompatibleLLM(
                    settings.llm_base_url,
                    settings.llm_model,
                    settings.llm_api_key,
                    settings.llm_timeout_seconds,
                )
            else:
                llm = _scripted_llm_for_scenario(scenario)

            agent = DialogueAgent(
                llm,
                order_client,
                prompts,
                restaurant_id,
                call_id,
                max_tool_rounds=settings.llm_max_tool_rounds,
            )
            ok, detail = await run_scenario(agent, scenario, use_graph=args.graph)
            mark = "PASS" if ok else "FAIL"
            print(f"[{mark}] {scenario['id']} {scenario['name']} — {detail}")
            if ok:
                passed += 1
        except Exception as exc:
            print(f"[ERROR] {scenario['id']} {scenario['name']} — {exc}")

    total = len(scenarios)
    print(f"\n{passed}/{total} scenarios passed ({args.mode} mode)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
