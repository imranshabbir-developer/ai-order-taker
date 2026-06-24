"""Shared scenario metadata for dialogue + API tests."""

from __future__ import annotations

SCENARIOS: list[dict[str, str | list[str]]] = [
    {
        "id": "01",
        "name": "Free-form bagel + modifiers",
        "utterance": "Everything bagel, cream cheese, lox, onions, olives, scoop the dough",
        "expected_status": "success",
    },
    {
        "id": "02a",
        "name": "Default modifiers silent",
        "utterances": [
            "Cream cheese sandwich",
            "And coffee with milk, no sugar",
        ],
        "expected_status": "success",
    },
    {
        "id": "02b",
        "name": "Challah requires variation",
        "utterance": "Two sourdough challahs",
        "expected_status": "clarification",
    },
    {
        "id": "03",
        "name": "Multi-category egg ambiguity",
        "utterance": "Sandwich with eggs",
        "expected_status": "clarification",
        "tool": "check_ambiguity",
    },
    {
        "id": "04",
        "name": "Split modifiers",
        "utterances": [
            "Mediterranean toast, no eggplant",
            "Another mediterranean toast with extra feta",
        ],
        "expected_status": "success",
    },
    {
        "id": "05",
        "name": "Conflicting milk / farina rule",
        "utterance": "Coffee with red and blue milk",
        "expected_status": "violation",
    },
    {
        "id": "06",
        "name": "Breakfast for two bundle",
        "utterance": "Breakfast for two",
        "expected_status": "success",
    },
    {
        "id": "07",
        "name": "Gift box + note",
        "utterance": "Gift box for 1-2 people, birthday note Happy Birthday",
        "expected_status": "success",
    },
    {
        "id": "08",
        "name": "Giant pizza bagel 24hr notice",
        "utterance": "Giant pizza bagel",
        "expected_status": "advance_notice",
    },
    {
        "id": "10",
        "name": "Special instructions tuna",
        "utterance": "Tuna sandwich, smear on both sides",
        "expected_status": "success",
    },
    {
        "id": "11",
        "name": "Pronunciation challah/bourekas",
        "utterances": [
            "Two braided sourdough challahs",
            "And a tray of barakas",
        ],
        "expected_status": "success",
    },
    {
        "id": "12",
        "name": "Spoken card payment",
        "utterances": [
            "Cream cheese sandwich",
            "That's correct, please checkout",
        ],
        "expected_status": "success",
        "requires_payment": True,
    },
    {
        "id": "13",
        "name": "SMS/spoken parity",
        "utterances": [
            "Cream cheese sandwich",
            "Coffee, no sugar",
        ],
        "expected_status": "success",
    },
    {
        "id": "14",
        "name": "Post-order add hash browns",
        "utterances": [
            "Cream cheese sandwich",
            "Add hash browns half lb",
        ],
        "expected_status": "success",
    },
]
