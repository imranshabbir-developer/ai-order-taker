from __future__ import annotations

import uuid

import pytest
from dialogue.agent import DialogueAgent
from dialogue.llm import LLMCompletion, LLMMessage, MockLLM
from dialogue.order_client import OrderApiClient, ToolResponse
from dialogue.prompts import load_prompts

from apps.voice_agent.providers.tts import TextTTSProvider
from apps.voice_agent.session import VoiceOrderSession


@pytest.fixture
def restaurant_id() -> str:
    return "hot_bagels_2nd_street"


@pytest.mark.asyncio
async def test_voice_session_text_turn(restaurant_id: str) -> None:
    call_id = f"voice-{uuid.uuid4().hex[:8]}"
    prompts = load_prompts(restaurant_id)

    mock_llm = MockLLM(
        [
            LLMCompletion(
                message=LLMMessage(
                    role="assistant",
                    tool_calls=[
                        {
                            "id": "tc1",
                            "type": "function",
                            "function": {
                                "name": "add_item",
                                "arguments": '{"item_term": "cream cheese sandwich"}',
                            },
                        }
                    ],
                )
            ),
            LLMCompletion(
                message=LLMMessage(role="assistant", content="Added to your order."),
            ),
        ]
    )

    order_client = OrderApiClient("http://test")

    async def reset_call(*_args, **_kwargs) -> None:
        return None

    async def invoke_tool(restaurant_id, call_id, tool, arguments=None):
        if tool == "add_item":
            return ToolResponse(
                status="success",
                message="Added.",
                line_id="line-1",
                cart={"lines": [{"item_id": "cream_cheese_sandwich"}]},
                spoken_summary="One cream cheese sandwich.",
                sms_summary="One cream cheese sandwich.",
            )
        return ToolResponse(status="not_found", message="missing")

    order_client.invoke_tool = invoke_tool  # type: ignore[method-assign]
    order_client.reset_call = reset_call  # type: ignore[method-assign]

    agent = DialogueAgent(
        mock_llm,
        order_client,
        prompts,
        restaurant_id,
        call_id,
    )

    session = VoiceOrderSession(
        restaurant_id=restaurant_id,
        call_id=call_id,
        llm=mock_llm,
        tts=TextTTSProvider(),
        local_playback=False,
    )
    session._agent = agent  # noqa: SLF001

    await session.start()
    turn = await session.process_text("cream cheese sandwich", speak=False)
    assert turn.normalized_transcript == "cream cheese sandwich"
    assert turn.agent.assistant_message
