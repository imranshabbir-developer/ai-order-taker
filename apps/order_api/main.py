from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from order_engine.catalog import MenuCatalog
from order_engine.models import OrderResultStatus

from apps.order_api.db.engine import (
    check_database,
    close_database,
    database_configured,
    init_database,
)
from apps.order_api.db.order_store import OrderStore
from apps.order_api.db.payment_store import PaymentStore
from apps.order_api.db.redis_cache import check_redis, close_redis, init_redis, redis_configured
from apps.order_api.db.seed import sync_restaurants_from_config
from apps.order_api.db.sms_store import SmsStore
from apps.order_api.schemas import (
    AddItemRequest,
    CallStartRequest,
    CallStartResponse,
    CheckoutRequest,
    EscalationRequest,
    EscalationResponse,
    OrderDetailResponse,
    OrderListResponse,
    OrderSummaryResponse,
    PaymentCaptureRequest,
    PaymentCaptureResponse,
    RemoveItemRequest,
    ResumeOrderRequest,
    SetModifierRequest,
    StoreStatusResponse,
    ToolInvokeRequest,
    ToolResponse,
)
from apps.order_api.settings import get_settings
from apps.order_api.use_cases import use_cases

RESTAURANT = "hot_bagels_2nd_street"
_order_store = OrderStore()
_payment_store = PaymentStore()
_sms_store = SmsStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    if get_settings().database_enabled:
        if await check_database():
            synced = await sync_restaurants_from_config(use_cases.config_root())
            print(f"PostgreSQL: connected ({synced} restaurants synced)")
        else:
            print(
                "WARNING: DATABASE_URL is set but PostgreSQL is unreachable. "
                "Run `alembic upgrade head` and verify credentials."
            )
    if redis_configured():
        if await init_redis():
            print("Redis: connected (session cache)")
        else:
            print("WARNING: REDIS_URL is set but Redis is unreachable.")
    yield
    await close_redis()
    await close_database()


app = FastAPI(
    title="Restaurants AI Agent — Order API",
    version="0.4.0",
    description="Deterministic order engine API. LLM/voice agents call tools through this service.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SCENARIOS: list[dict] = [
    {
        "id": "01",
        "name": "Free-form bagel + modifiers",
        "utterance": "Everything bagel, cream cheese, lox, onions, olives, scoop the dough",
    },
    {
        "id": "02a",
        "name": "Default modifiers silent",
        "utterance": "Cream cheese sandwich + coffee milk no sugar",
    },
    {"id": "02b", "name": "Challah requires variation", "utterance": "2 sourdough challahs"},
    {"id": "03", "name": "Multi-category egg ambiguity", "utterance": "Sandwich with eggs"},
    {
        "id": "04",
        "name": "Split modifiers",
        "utterance": "Two Mediterranean toasts — one no eggplant, one extra feta",
    },
    {
        "id": "05",
        "name": "Conflicting milk / farina rule",
        "utterance": "Coffee red+blue milk; farina with coffee side",
    },
    {"id": "06", "name": "Breakfast for two bundle", "utterance": "Breakfast for two"},
    {"id": "07", "name": "Gift box + note", "utterance": "Gift box for 1-2 + birthday note"},
    {"id": "08", "name": "Giant pizza bagel 24hr notice", "utterance": "Giant pizza bagel"},
    {
        "id": "10",
        "name": "Special instructions tuna",
        "utterance": "Tuna sandwich, smear on both sides",
    },
    {
        "id": "11",
        "name": "Pronunciation challah/bourekas",
        "utterance": "Challahs + tray of barakas",
    },
    {"id": "12", "name": "Spoken card payment", "utterance": "Pay with card after checkout"},
    {"id": "13", "name": "SMS/spoken parity", "utterance": "Demo order parity check"},
    {"id": "14", "name": "Post-order add hash browns", "utterance": "Add hash browns half lb"},
]


@app.get("/health")
async def health() -> dict[str, str]:
    body: dict[str, str] = {"status": "ok"}
    if database_configured():
        db_ok = await check_database()
        body["database"] = "connected" if db_ok else "unavailable"
    else:
        body["database"] = "disabled"
    if redis_configured():
        redis_ok = await check_redis()
        body["redis"] = "connected" if redis_ok else "unavailable"
    else:
        body["redis"] = "disabled"
    return body


@app.get("/v1/restaurants")
def list_restaurants() -> dict[str, list[dict]]:
    restaurants = []
    for p in use_cases.config_root().iterdir():
        if p.is_dir():
            bundle = use_cases.get_bundle(p.name)
            restaurants.append(
                {
                    "id": p.name,
                    "name": bundle.menu.get("name", p.name),
                    "is_mock": bundle.is_mock,
                    "item_count": len(bundle.menu.get("items", [])),
                }
            )
    return {"restaurants": restaurants}


@app.get("/v1/restaurants/{restaurant_id}/config")
def get_config(restaurant_id: str) -> dict:
    bundle = use_cases.get_bundle(restaurant_id)
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
    catalog = MenuCatalog.from_path(use_cases.config_dir(restaurant_id))
    by_category = catalog.items_by_category()
    return {
        "restaurant_id": restaurant_id,
        "categories": {
            cat: [i.model_dump() for i in items] for cat, items in sorted(by_category.items())
        },
        "bundles": [b.model_dump() for b in catalog.config.bundles],
        "modifiers": [m.model_dump() for m in catalog.config.modifiers],
    }


@app.get("/v1/restaurants/{restaurant_id}/scenarios")
def list_scenarios() -> dict[str, list]:
    return {"scenarios": SCENARIOS}


@app.get("/v1/restaurants/{restaurant_id}/store-status", response_model=StoreStatusResponse)
def get_store_status(restaurant_id: str) -> StoreStatusResponse:
    status = use_cases.store_status(restaurant_id)
    return StoreStatusResponse(**status)


@app.post(
    "/v1/restaurants/{restaurant_id}/orders/{order_id}/payment",
    response_model=PaymentCaptureResponse,
)
async def capture_payment(
    restaurant_id: str,
    order_id: str,
    body: PaymentCaptureRequest,
    call_id: str = "",
) -> PaymentCaptureResponse:
    return await use_cases.capture_payment(
        restaurant_id,
        order_id,
        card_number=body.card_number,
        exp_month=body.exp_month,
        exp_year=body.exp_year,
        cvv=body.cvv,
        call_id=call_id,
    )


@app.post(
    "/v1/restaurants/{restaurant_id}/calls/{call_id}/start",
    response_model=CallStartResponse,
)
async def start_call(
    restaurant_id: str, call_id: str, body: CallStartRequest | None = None
) -> CallStartResponse:
    payload = body or CallStartRequest()
    result = await use_cases.start_call(restaurant_id, call_id, payload.caller_phone)
    return CallStartResponse(**result)


@app.post(
    "/v1/restaurants/{restaurant_id}/calls/{call_id}/escalate",
    response_model=EscalationResponse,
)
async def escalate_call(
    restaurant_id: str,
    call_id: str,
    body: EscalationRequest | None = None,
) -> EscalationResponse:
    payload = body or EscalationRequest()
    result = use_cases.escalate_call(restaurant_id, call_id, payload.reason)
    return EscalationResponse(**result)


@app.get("/v1/restaurants/{restaurant_id}/orders/{order_id}/sms")
async def list_order_sms(restaurant_id: str, order_id: str) -> dict:
    try:
        oid = UUID(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid order ID.") from exc
    record = await _order_store.get_order(oid)
    if record is None or record.restaurant_id != restaurant_id:
        raise HTTPException(status_code=404, detail="Order not found.")
    messages = await _sms_store.list_for_order(oid)
    return {
        "order_id": order_id,
        "messages": [
            {
                "sms_id": m.sms_id,
                "to_phone": m.to_phone,
                "body": m.body,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@app.get("/v1/restaurants/{restaurant_id}/orders/{order_id}/payments")
async def list_order_payments(restaurant_id: str, order_id: str) -> dict:
    try:
        oid = UUID(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid order ID.") from exc
    record = await _order_store.get_order(oid)
    if record is None or record.restaurant_id != restaurant_id:
        raise HTTPException(status_code=404, detail="Order not found.")
    charges = await _payment_store.list_for_order(oid)
    return {
        "order_id": order_id,
        "payments": [
            {
                "charge_id": c.charge_id,
                "amount_cents": c.amount_cents,
                "last_four": c.last_four,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in charges
        ],
    }


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/reset")
async def reset_call(restaurant_id: str, call_id: str) -> dict[str, str]:
    await use_cases.reset_call(restaurant_id, call_id)
    return {"status": "reset", "call_id": call_id}


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/tool")
async def invoke_tool(restaurant_id: str, call_id: str, body: ToolInvokeRequest) -> ToolResponse:
    return await use_cases.invoke_tool(restaurant_id, call_id, body.tool, body.arguments)


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/tools/add_item")
async def add_item(restaurant_id: str, call_id: str, body: AddItemRequest) -> ToolResponse:
    return await use_cases.add_item(
        restaurant_id,
        call_id,
        item_term=body.item_term,
        item_id=body.item_id,
        requested_modifiers=body.requested_modifiers,
        quantity=body.quantity,
        special_instructions=body.special_instructions,
    )


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/tools/remove_item")
async def remove_item(restaurant_id: str, call_id: str, body: RemoveItemRequest) -> ToolResponse:
    return await use_cases.remove_item(restaurant_id, call_id, body.line_id)


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/tools/set_modifier")
async def set_modifier(restaurant_id: str, call_id: str, body: SetModifierRequest) -> ToolResponse:
    return await use_cases.set_modifiers(
        restaurant_id, call_id, body.line_id, body.requested_modifiers
    )


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/checkout")
async def checkout(restaurant_id: str, call_id: str, body: CheckoutRequest) -> ToolResponse:
    return await use_cases.checkout(restaurant_id, call_id, body.customer_phone)


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/resume-from-phone")
async def resume_from_phone(
    restaurant_id: str, call_id: str, body: ResumeOrderRequest
) -> ToolResponse:
    return await use_cases.resume_order_by_phone(restaurant_id, call_id, body.customer_phone)


@app.get("/v1/restaurants/{restaurant_id}/orders", response_model=OrderListResponse)
async def list_orders(
    restaurant_id: str,
    day: str = "today",
    limit: int = 100,
) -> OrderListResponse:
    """List orders filtered by calendar day in restaurant timezone (today|tomorrow|all)."""
    day_filter = day.strip().lower()
    if day_filter not in {"today", "tomorrow", "all"}:
        raise HTTPException(status_code=400, detail="day must be today, tomorrow, or all")
    items, tz = await use_cases.list_orders(restaurant_id, day=day_filter, limit=min(limit, 200))
    return OrderListResponse(filter=day_filter, timezone=tz, count=len(items), orders=items)


@app.get("/v1/restaurants/{restaurant_id}/orders/by-phone/{customer_phone}")
async def get_order_by_phone(restaurant_id: str, customer_phone: str) -> OrderSummaryResponse:
    record = await _order_store.find_latest_open_by_phone(restaurant_id, customer_phone)
    if record is None:
        raise HTTPException(status_code=404, detail="No open order found for that phone number.")
    return OrderSummaryResponse(
        order_id=str(record.id),
        restaurant_id=record.restaurant_id,
        call_id=record.call_id,
        customer_phone=record.customer_phone,
        status=record.status,
        cart=record.cart.model_dump(),
        spoken_summary=record.spoken_summary,
        sms_summary=record.sms_summary,
        created_at=record.created_at.isoformat() if record.created_at else None,
        total_cents=record.cart.total_cents,
    )


@app.get("/v1/restaurants/{restaurant_id}/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order(restaurant_id: str, order_id: str) -> OrderDetailResponse:
    try:
        oid = UUID(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid order ID.") from exc
    record = await use_cases._get_order_record(oid)
    if record is None or record.restaurant_id != restaurant_id:
        raise HTTPException(status_code=404, detail="Order not found.")
    payments = await _payment_store.list_for_order(oid)
    messages = await _sms_store.list_for_order(oid)
    return OrderDetailResponse(
        order_id=str(record.id),
        restaurant_id=record.restaurant_id,
        call_id=record.call_id,
        customer_phone=record.customer_phone,
        status=record.status,
        cart=record.cart.model_dump(),
        spoken_summary=record.spoken_summary,
        sms_summary=record.sms_summary,
        created_at=record.created_at.isoformat() if record.created_at else None,
        total_cents=record.cart.total_cents,
        payments=[
            {
                "charge_id": p.charge_id,
                "amount_cents": p.amount_cents,
                "last_four": p.last_four,
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in payments
        ],
        sms_messages=[
            {
                "sms_id": m.sms_id,
                "to_phone": m.to_phone,
                "body": m.body,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    )


@app.get("/v1/restaurants/{restaurant_id}/calls/{call_id}/cart")
async def get_cart(restaurant_id: str, call_id: str) -> ToolResponse:
    return await use_cases.get_cart(restaurant_id, call_id)


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/tools/check_ambiguity")
async def check_ambiguity(restaurant_id: str, call_id: str, query: str) -> ToolResponse:
    return await use_cases.check_ambiguity(restaurant_id, call_id, query)


@app.post("/v1/restaurants/{restaurant_id}/calls/{call_id}/scenarios/{scenario_id}/run")
async def run_scenario(restaurant_id: str, call_id: str, scenario_id: str) -> ToolResponse:
    """Run a single HOT BAGELS scenario against the current session."""
    await use_cases.reset_call(restaurant_id, call_id)
    service = await use_cases.get_service(restaurant_id, call_id)
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
        result = (
            r
            if r.status == OrderResultStatus.VIOLATION
            else service.add_item("farina", ["coffee on side"])
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
        result = _AdapterResult(
            OrderResultStatus.SUCCESS
            if matches and matches[0][0].id == "bourekas_tray"
            else OrderResultStatus.NOT_FOUND,
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

    await use_cases.persist_session(restaurant_id, call_id, service)
    return use_cases.build_response(service, result)


class _AdapterResult:
    def __init__(self, status: OrderResultStatus, message: str) -> None:
        self.status = status
        self.message = message
        self.line_id: str | None = None
        self.options: list[str] = []
