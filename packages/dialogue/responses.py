from __future__ import annotations

from dialogue.order_client import ToolResponse


def format_tool_result(tool_name: str, response: ToolResponse) -> str:
    """Convert order-engine tool output into LLM-facing context."""
    parts = [f"Tool: {tool_name}", f"Status: {response.status}", f"Message: {response.message}"]

    if response.options:
        numbered = "; ".join(f"{i + 1}. {opt}" for i, opt in enumerate(response.options))
        parts.append(f"Options: {numbered}")

    if response.line_id:
        parts.append(f"line_id: {response.line_id}")

    if response.spoken_summary:
        parts.append(f"spoken_summary: {response.spoken_summary}")

    if response.order_id:
        parts.append(f"order_id: {response.order_id}")

    status = response.status.lower()
    if status == "clarification":
        parts.append(
            "ACTION: Ask the customer to choose one option, then call add_item or "
            "set_modifier with their choice."
        )
    elif status == "violation":
        parts.append(
            "ACTION: Explain the rule violation politely and ask how they would like to proceed."
        )
    elif status == "advance_notice":
        parts.append(
            "ACTION: Inform the customer about the advance-notice requirement. "
            "Do not add the item unless they accept."
        )
    elif status == "not_found":
        parts.append("ACTION: Ask the customer to rephrase or pick from similar menu items.")
    elif status == "success" and tool_name == "get_cart":
        parts.append("ACTION: Read back spoken_summary exactly — do not invent items or prices.")
    elif status == "success" and tool_name == "checkout":
        parts.append("ACTION: Confirm the order is placed and share the order_id if present.")

    return "\n".join(parts)


def customer_facing_hint(response: ToolResponse) -> str | None:
    """Short hint for TTS when the agent should defer to engine text."""
    if response.status == "clarification" and response.options:
        return response.message
    if response.status in ("violation", "advance_notice", "not_found"):
        return response.message
    if response.spoken_summary and response.status == "success":
        return response.spoken_summary
    return None
