from __future__ import annotations

from enum import StrEnum
from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict


class DialoguePhase(StrEnum):
    GREETING = "greeting"
    ORDERING = "ordering"
    CLARIFYING = "clarifying"
    CONFIRMING = "confirming"
    PAYMENT = "payment"
    COMPLETE = "complete"
    ESCALATED = "escalated"


class GraphState(TypedDict, total=False):
    restaurant_id: str
    call_id: str
    phase: str
    user_message: str
    assistant_message: str
    done: bool
    last_tool: str | None
    last_status: str | None


def advance_phase(phase: DialoguePhase, tool_name: str, status: str) -> DialoguePhase:
    normalized = status.lower()
    if tool_name == "checkout" and normalized == "success":
        return DialoguePhase.COMPLETE
    if normalized == "clarification":
        return DialoguePhase.CLARIFYING
    if tool_name == "get_cart" and normalized == "success":
        return DialoguePhase.CONFIRMING
    if phase == DialoguePhase.GREETING:
        return DialoguePhase.ORDERING
    if phase == DialoguePhase.CLARIFYING and normalized == "success":
        return DialoguePhase.ORDERING
    if phase == DialoguePhase.CONFIRMING and tool_name == "add_item":
        return DialoguePhase.ORDERING
    return phase


def build_dialogue_graph(agent_runner: Any) -> Any:
    """LangGraph wrapper — one compiled step per user message."""

    async def run_turn(state: GraphState) -> GraphState:
        result = await agent_runner.handle_user_message(state["user_message"])
        last_status = result.tool_results[-1].status if result.tool_results else None
        return {
            **state,
            "phase": result.phase.value,
            "assistant_message": result.assistant_message,
            "done": result.done,
            "last_tool": "tool" if result.tool_results else None,
            "last_status": last_status,
        }

    graph: StateGraph = StateGraph(GraphState)
    graph.add_node("turn", run_turn)
    graph.set_entry_point("turn")
    graph.add_edge("turn", END)
    return graph.compile()
