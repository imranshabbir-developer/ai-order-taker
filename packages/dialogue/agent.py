from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dialogue.graph import DialoguePhase, advance_phase
from dialogue.llm import LLMClient, parse_tool_arguments
from dialogue.order_client import OrderApiClient, ToolResponse
from dialogue.prompts import RestaurantPrompts
from dialogue.responses import customer_facing_hint, format_tool_result
from dialogue.tools import ORDER_TOOLS


@dataclass
class AgentTurnResult:
    assistant_message: str
    phase: DialoguePhase
    tool_results: list[ToolResponse] = field(default_factory=list)
    done: bool = False
    messages: list[dict[str, Any]] = field(default_factory=list)


class DialogueAgent:
    """Text dialogue brain — LLM interprets speech, order engine is authoritative."""

    def __init__(
        self,
        llm: LLMClient,
        order_client: OrderApiClient,
        prompts: RestaurantPrompts,
        restaurant_id: str,
        call_id: str,
        *,
        max_tool_rounds: int = 8,
    ) -> None:
        self._llm = llm
        self._order = order_client
        self._prompts = prompts
        self._restaurant_id = restaurant_id
        self._call_id = call_id
        self._max_tool_rounds = max_tool_rounds
        self._phase = DialoguePhase.GREETING
        self._messages: list[dict[str, Any]] = []
        self._bootstrapped = False

    @property
    def restaurant_id(self) -> str:
        return self._restaurant_id

    @property
    def call_id(self) -> str:
        return self._call_id

    @property
    def phase(self) -> DialoguePhase:
        return self._phase

    @property
    def messages(self) -> list[dict[str, Any]]:
        return list(self._messages)

    async def reset(self) -> None:
        await self._order.reset_call(self._restaurant_id, self._call_id)
        self._phase = DialoguePhase.GREETING
        self._messages = []
        self._bootstrapped = False

    def _ensure_system(self) -> None:
        if self._bootstrapped:
            return
        self._messages = [
            {"role": "system", "content": self._prompts.render_system(self._phase.value)},
        ]
        self._bootstrapped = True

    async def start(self) -> AgentTurnResult:
        await self.reset()
        self._ensure_system()
        greeting = self._prompts.render_greeting()
        self._messages.append({"role": "assistant", "content": greeting})
        self._phase = DialoguePhase.ORDERING
        self._messages[0] = {
            "role": "system",
            "content": self._prompts.render_system(self._phase.value),
        }
        return AgentTurnResult(
            assistant_message=greeting,
            phase=self._phase,
            messages=list(self._messages),
        )

    async def handle_user_message(self, user_text: str) -> AgentTurnResult:
        self._ensure_system()
        self._messages.append({"role": "user", "content": user_text})

        tool_results: list[ToolResponse] = []
        rounds = 0
        llm_retries = 0

        while rounds < self._max_tool_rounds:
            rounds += 1
            try:
                completion = await self._llm.complete(self._messages, ORDER_TOOLS)
            except Exception as exc:
                llm_retries += 1
                if llm_retries > 2:
                    message = (
                        "I'm having trouble reaching the ordering system. "
                        "Please try again in a moment."
                    )
                    self._messages.append({"role": "assistant", "content": message})
                    return AgentTurnResult(
                        assistant_message=message,
                        phase=self._phase,
                        tool_results=tool_results,
                        messages=list(self._messages),
                    )
                self._messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Use the tool calling API with valid JSON arguments only. "
                            f"Previous error: {exc}"
                        ),
                    }
                )
                continue
            assistant = completion.message

            if assistant.tool_calls:
                self._messages.append(
                    {
                        "role": "assistant",
                        "content": assistant.content,
                        "tool_calls": assistant.tool_calls,
                    }
                )
                for tool_call in assistant.tool_calls:
                    fn = tool_call["function"]
                    tool_name = fn["name"]
                    arguments = parse_tool_arguments(fn.get("arguments", "{}"))
                    result = await self._order.invoke_tool(
                        self._restaurant_id,
                        self._call_id,
                        tool_name,
                        arguments,
                    )
                    tool_results.append(result)
                    self._phase = advance_phase(self._phase, tool_name, result.status)
                    self._messages[0] = {
                        "role": "system",
                        "content": self._prompts.render_system(self._phase.value),
                    }
                    self._messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": tool_name,
                            "content": format_tool_result(tool_name, result),
                        }
                    )
                continue

            content = (assistant.content or "").strip()
            if not content and tool_results:
                hint = customer_facing_hint(tool_results[-1])
                content = hint or tool_results[-1].message

            self._messages.append({"role": "assistant", "content": content})
            done = self._phase == DialoguePhase.COMPLETE
            return AgentTurnResult(
                assistant_message=content,
                phase=self._phase,
                tool_results=tool_results,
                done=done,
                messages=list(self._messages),
            )

        fallback = "Let me confirm that with the kitchen system — one moment."
        self._messages.append({"role": "assistant", "content": fallback})
        return AgentTurnResult(
            assistant_message=fallback,
            phase=self._phase,
            tool_results=tool_results,
            done=False,
            messages=list(self._messages),
        )
