from __future__ import annotations

import json
import uuid

import httpx
import pytest
from dialogue.agent import DialogueAgent
from dialogue.llm import LLMCompletion, LLMMessage, MockLLM
from dialogue.order_client import OrderApiClient
from dialogue.prompts import load_prompts


@pytest.fixture
def restaurant_id() -> str:
    return "hot_bagels_2nd_street"


@pytest.fixture
def prompts(restaurant_id: str):
    return load_prompts(restaurant_id)


@pytest.mark.asyncio
async def test_agent_add_item_via_mock_llm(restaurant_id: str, prompts) -> None:
    call_id = f"dlg-{uuid.uuid4().hex[:8]}"

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/reset"):
            return httpx.Response(200, json={"status": "reset", "call_id": call_id})
        if request.url.path.endswith("/tool"):
            body = json.loads(request.content)
            assert body["tool"] == "add_item"
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "message": "Added cream cheese sandwich.",
                    "line_id": "line-1",
                    "options": [],
                    "cart": {"lines": [{"item_id": "cream_cheese_sandwich"}]},
                    "spoken_summary": "One cream cheese sandwich.",
                    "sms_summary": "One cream cheese sandwich.",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        order_client = OrderApiClient("http://test")
        order_client._base_url = "http://test"  # noqa: SLF001

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
                                    "arguments": json.dumps({"item_term": "cream cheese sandwich"}),
                                },
                            }
                        ],
                    )
                ),
                LLMCompletion(
                    message=LLMMessage(
                        role="assistant",
                        content="Added a cream cheese sandwich to your order.",
                    )
                ),
            ]
        )

        agent = DialogueAgent(
            mock_llm,
            order_client,
            prompts,
            restaurant_id,
            call_id,
        )

        # Patch invoke_tool to use mock transport
        async def invoke_tool(restaurant_id, call_id, tool, arguments=None):
            payload = {"tool": tool, "arguments": arguments or {}}
            response = await http.post(
                f"/v1/restaurants/{restaurant_id}/calls/{call_id}/tool",
                json=payload,
            )
            from dialogue.order_client import ToolResponse

            return ToolResponse.from_api(response.json())

        order_client.invoke_tool = invoke_tool  # type: ignore[method-assign]
        order_client.reset_call = lambda *a, **k: None  # type: ignore[method-assign, assignment]

        turn = await agent.handle_user_message("I'd like a cream cheese sandwich")
        assert turn.tool_results
        assert turn.tool_results[0].status == "success"
        assert "cream cheese" in turn.assistant_message.lower()
