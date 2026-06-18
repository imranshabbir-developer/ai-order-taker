from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TOOL_NAMES = (
    "add_item",
    "remove_item",
    "set_modifier",
    "get_cart",
    "check_ambiguity",
    "checkout",
)

ORDER_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "add_item",
            "description": (
                "Add a menu item to the customer's cart. Use item_term for natural "
                "language (e.g. 'everything bagel', 'cream cheese sandwich'). "
                "Pass requested_modifiers as spoken by the customer."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "item_term": {
                        "type": "string",
                        "description": "Menu item name or description from the customer.",
                    },
                    "item_id": {
                        "type": "string",
                        "description": "Exact menu item id when already disambiguated.",
                    },
                    "requested_modifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Modifier phrases (e.g. 'cream cheese', 'no sugar').",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "How many of this item.",
                        "default": 1,
                    },
                    "special_instructions": {
                        "type": "string",
                        "description": "Special prep notes for this line.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_item",
            "description": "Remove a line from the cart by line_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "line_id": {"type": "string", "description": "Cart line id to remove."},
                },
                "required": ["line_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_modifier",
            "description": "Replace modifiers on an existing cart line (after clarification).",
            "parameters": {
                "type": "object",
                "properties": {
                    "line_id": {"type": "string"},
                    "requested_modifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["line_id", "requested_modifiers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cart",
            "description": (
                "Get the current cart with spoken_summary for read-back. "
                "Always use before confirming the order."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_ambiguity",
            "description": (
                "Check if a customer phrase matches multiple menu categories before adding items."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Customer phrase to check."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "checkout",
            "description": (
                "Finalize the order after customer confirms. Requires a non-empty cart."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_phone": {
                        "type": "string",
                        "description": "Customer phone for order lookup (optional at pickup).",
                    },
                },
            },
        },
    },
]


def tools_json_path(restaurant_id: str, config_root: Path | None = None) -> Path:
    root = config_root or Path(__file__).resolve().parents[2] / "config" / "restaurants"
    return root / restaurant_id / "tools.json"


def write_tools_json(restaurant_id: str, config_root: Path | None = None) -> Path:
    path = tools_json_path(restaurant_id, config_root)
    path.write_text(json.dumps({"tools": ORDER_TOOLS}, indent=2) + "\n", encoding="utf-8")
    return path


def load_tools_json(restaurant_id: str, config_root: Path | None = None) -> list[dict[str, Any]]:
    path = tools_json_path(restaurant_id, config_root)
    if not path.exists():
        write_tools_json(restaurant_id, config_root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    tools = payload.get("tools", ORDER_TOOLS)
    return tools if isinstance(tools, list) else ORDER_TOOLS
