from __future__ import annotations

from dialogue.graph import DialoguePhase, advance_phase
from dialogue.order_client import ToolResponse
from dialogue.responses import format_tool_result
from dialogue.tools import ORDER_TOOLS, TOOL_NAMES, write_tools_json


def test_tool_names_match_definitions() -> None:
    names = {t["function"]["name"] for t in ORDER_TOOLS}
    assert names == set(TOOL_NAMES)


def test_write_tools_json(tmp_path) -> None:
    config_root = tmp_path / "restaurants"
    (config_root / "demo").mkdir(parents=True)
    path = write_tools_json("demo", config_root)
    assert path.exists()
    assert "add_item" in path.read_text(encoding="utf-8")


def test_advance_phase_clarification() -> None:
    phase = advance_phase(DialoguePhase.ORDERING, "add_item", "clarification")
    assert phase == DialoguePhase.CLARIFYING


def test_advance_phase_checkout_complete() -> None:
    phase = advance_phase(DialoguePhase.CONFIRMING, "checkout", "success")
    assert phase == DialoguePhase.COMPLETE


def test_format_tool_result_clarification() -> None:
    text = format_tool_result(
        "add_item",
        ToolResponse(
            status="clarification",
            message="Which style?",
            options=["Braided", "Round"],
        ),
    )
    assert "CLARIFICATION" in text or "clarification" in text.lower()
    assert "Braided" in text
