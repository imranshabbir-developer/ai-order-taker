from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from order_engine.catalog import MenuCatalog
from order_engine.config_loader import RestaurantConfigBundle
from order_engine.models import OrderResultStatus
from order_engine.order_service import OrderService

CONFIG_ROOT = Path(__file__).resolve().parents[2] / "config" / "restaurants"

app = FastAPI(
    title="Restaurants AI Agent — Order API",
    version="0.2.0",
    description="Deterministic order engine API. LLM/voice agents call tools through this service.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_sessions: dict[str, OrderService] = {}
_config_cache: dict[str, RestaurantConfigBundle] = {}


def _config_dir(restaurant_id: str) -> Path:
    path = CONFIG_ROOT / restaurant_id
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Restaurant '{restaurant_id}' not found")
    return path


def _get_bundle(restaurant_id: str) -> RestaurantConfigBundle:
    if restaurant_id not in _config_cache:
        _config_cache[restaurant_id] = RestaurantConfigBundle.load(_config_dir(restaurant_id))
    return _config_cache[restaurant_id]


def _get_service(restaurant_id: str, call_id: str) -> OrderService:
    key = f"{restaurant_id}:{call_id}"
    if key not in _sessions:
        catalog = MenuCatalog.from_path(_config_dir(restaurant_id))
        _sessions[key] = OrderService(catalog)
    return _sessions[key]


class AddItemRequest(BaseModel):
    item_term: str = ""
    requested_modifiers: list[str] = Field(default_factory=list)
    quantity: int = 1
    special_instructions: str = ""
    item_id: str | None = None


class ToolResponse(BaseModel):
    status: str
    message: str
    line_id: str | None = None
    options: list[str] = Field(default_factory=list)
    cart: dict | None = None
    spoken_summary: str | None = None
    sms_summary: str | None = None


SCENARIOS: list[dict] = [
    {"id": "01", "name": "Free-form bagel + modifiers", "utterance": "Everything bagel, cream cheese, lox, onions, olives, scoop the dough"},
    {"id": "02a", "name": "Default modifiers silent", "utterance": "Cream cheese sandwich + coffee milk no sugar"},
    {"id": "02b", "name": "Challah requires variation", "utterance": "2 sourdough challahs"},
    {"id": "03", "name": "Multi-category egg ambiguity", "utterance": "Sandwich with eggs"},
    {"id": "04", "name": "Split modifiers", "utterance": "Two Mediterranean toasts — one no eggplant, one extra feta"},
    {"id": "05", "name": "Conflicting milk / farina rule", "utterance": "Coffee red+blue milk; farina with coffee side"},
    {"id": "06", "name": "Breakfast for two bundle", "utterance": "Breakfast for two"},
    {"id": "07", "name": "Gift box + note", "utterance": "Gift box for 1-2 + birthday note"},
    {"id": "08", "name": "Giant pizza bagel 24hr notice", "utterance": "Giant pizza bagel"},
    {"id": "10", "name": "Special instructions tuna", "utterance": "Tuna sandwich, smear on both sides"},
    {"id": "11", "name": "Pronunciation challah/bourekas", "utterance": "Challahs + tray of barakas"},
    {"id": "13", "name": "SMS/spoken parity", "utterance": "Demo order parity check"},
    {"id": "14", "name": "Post-order add hash browns", "utterance": "Add hash browns half lb"},
]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/restaurants")
def list_restaurants() -> dict[str, list[dict]]:
    restaurants = []
    for p in CONFIG_ROOT.iterdir():
        if p.is_dir():
            bundle = _get_bundle(p.name)
            restaurants.append({
                "id": p.name,
                "name": bundle.menu.get("name", p.name),
                "is_mock": bundle.is_mock,
                "item_count": len(bundle.menu.get("items", [])),
            })
    return {"restaurants": restaurants}


@app.get("/v1/restaurants/{restaurant_id}/config")
def get_config(restaurant_id: str) -> dict:
    bundle = _get_bundle(restaurant_id)
    return {
        "restaurant_id": restaurant_id,
        "is_mock": bundle.is_mock,
        "menu_summary": {
            "name": bundle.menu.get("name"),
            "item_count": len(bundle.menu.get("items", [])),
            "bundle_count": len(bundle.menu.get("bundles", [])),
            "modifier_count": len(bundle.menu.get("modifiers", [])),
        },
        "operations": bundle.operations,
        "integrations": bundle.integrations,
        "pronunciations": bundle.pronunciations,
    }


@app.get("/v1/restaurants/{restaurant_id}/menu")
def get_menu(restaurant_id: str) -> dict:
    catalog = MenuCatalog.from_path(_config_dir(restaurant_id))
    by_category = catalog.items_by_category()
    return {
        "restaurant_id": restaurant_id,
        "categories": {
            cat: [i.model_dump() for i in items]
            for cat, items in sorted(by_category.items())
        },
        "bundles": [b.model_dump() for b in catalog.config.bundles],
        "modifiers": [m.model_dump() for m in catalog.config.modifiers],
    }


@app.get("/v1/restaurants/{restaurant_id}/scenarios")
def list_scenarios() -> dict[str, list]:
    return {"scenarios": SCENARIOS}


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/reset")
def reset_call(restaurant_id: str, call_id: str) -> dict[str, str]:
    key = f"{restaurant_id}:{call_id}"
    _sessions.pop(key, None)
    return {"status": "reset", "call_id": call_id}


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/tools/add_item")
def add_item(restaurant_id: str, call_id: str, body: AddItemRequest) -> ToolResponse:
    service = _get_service(restaurant_id, call_id)
    if body.item_id:
        result = service.add_item_by_id(
            body.item_id,
            requested_modifiers=body.requested_modifiers,
            quantity=body.quantity,
            special_instructions=body.special_instructions,
        )
    else:
        result = service.add_item(
            body.item_term,
            requested_modifiers=body.requested_modifiers,
            quantity=body.quantity,
            special_instructions=body.special_instructions,
        )
    spoken, sms = service.get_summary()
    return ToolResponse(
        status=result.status.value,
        message=result.message,
        line_id=result.line_id,
        options=result.options,
        cart=result.cart.model_dump() if result.cart else None,
        spoken_summary=spoken,
        sms_summary=sms,
    )


@app.get("/v1/restaurants/{restaurant_id}/calls/{call_id}/cart")
def get_cart(restaurant_id: str, call_id: str) -> ToolResponse:
    service = _get_service(restaurant_id, call_id)
    spoken, sms = service.get_summary()
    return ToolResponse(
        status=OrderResultStatus.SUCCESS.value,
        message="Current cart",
        cart=service.cart.model_dump(),
        spoken_summary=spoken,
        sms_summary=sms,
    )


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/tools/check_ambiguity")
def check_ambiguity(restaurant_id: str, call_id: str, query: str) -> ToolResponse:
    service = _get_service(restaurant_id, call_id)
    result = service.check_ambiguity(query)
    return ToolResponse(
        status=result.status.value,
        message=result.message,
        options=result.options,
        cart=result.cart.model_dump() if result.cart else None,
    )


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/scenarios/{scenario_id}/run")
def run_scenario(restaurant_id: str, call_id: str, scenario_id: str) -> ToolResponse:
    """Run a single HOT BAGELS scenario against a fresh logical flow on current session."""
    service = _get_service(restaurant_id, call_id)
    sid = scenario_id.lower().replace("-", "")

    if sid == "01":
        result = service.add_item(
            "everything bagel",
            ["cream cheese", "smoked lox", "red onions", "olives"],
            special_instructions="scoop the dough",
        )
    elif sid == "02a":
        service.add_item("cream cheese sandwich")
        result = service.add_item("coffee", ["milk", "no sugar"])
    elif sid == "02b":
        result = service.add_item("sourdough challah", quantity=2)
    elif sid == "03":
        result = service.check_ambiguity("sandwich with eggs")
    elif sid == "04":
        service.add_item("mediterranean toast", ["no eggplant"])
        result = service.add_item("mediterranean toast", ["extra feta"])
    elif sid == "05":
        r = service.add_item("coffee", ["red milk", "blue milk"])
        result = r if r.status == OrderResultStatus.VIOLATION else service.add_item(
            "farina", ["coffee on side"]
        )
    elif sid == "06":
        result = service.add_item("breakfast for two")
    elif sid == "07":
        result = service.add_item("gift box for 1-2 people", special_instructions="Happy Birthday!")
    elif sid == "08":
        result = service.add_item("giant pizza bagel")
    elif sid == "10":
        result = service.add_item("tuna sandwich", special_instructions="Smear tuna on both sides")
    elif sid == "11":
        service.add_item_by_id("sourdough_challah", ["braided"], quantity=2)
        matches = service.catalog.search_items("barakas")
        result = AddItemResultAdapter(
            OrderResultStatus.SUCCESS if matches and matches[0][0].id == "bourekas_tray" else OrderResultStatus.NOT_FOUND,
            f"Matched bourekas: {matches[0][0].name if matches else 'none'}",
        )
    elif sid == "13":
        service.add_item("cream cheese sandwich")
        result = service.add_item("coffee", ["no sugar"])
    elif sid == "14":
        service.add_item("cream cheese sandwich")
        result = service.add_item("hash browns half lb")
    else:
        raise HTTPException(status_code=404, detail=f"Unknown scenario {scenario_id}")

    spoken, sms = service.get_summary()
    status = result.status.value if hasattr(result, "status") else OrderResultStatus.SUCCESS.value
    message = result.message if hasattr(result, "message") else "Done"
    options = getattr(result, "options", []) or []
    return ToolResponse(
        status=status,
        message=message,
        options=list(options),
        cart=service.cart.model_dump(),
        spoken_summary=spoken,
        sms_summary=sms,
    )


class AddItemResultAdapter:
    def __init__(self, status: OrderResultStatus, message: str) -> None:
        self.status = status
        self.message = message
        self.options: list[str] = []
