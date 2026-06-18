from __future__ import annotations

import os
import uuid

import pytest
from httpx import AsyncClient

from apps.order_api.settings import get_settings
from tests.integration.conftest import RESTAURANT_ID, api_path

SCENARIO_IDS = ["01", "02a", "02b", "03", "04", "05", "06", "07", "08", "10", "11", "13", "14"]


async def _reset(client: AsyncClient, call_id: str) -> None:
    r = await client.post(api_path(RESTAURANT_ID, call_id, "/reset"))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] in ("disabled", "connected", "unavailable")


@pytest.mark.asyncio
async def test_add_item_and_get_cart(client: AsyncClient, call_id: str) -> None:
    await _reset(client, call_id)
    r = await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/add_item"),
        json={
            "item_term": "everything bagel",
            "requested_modifiers": ["cream cheese", "smoked lox"],
            "special_instructions": "scoop the dough",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["line_id"]
    assert len(body["cart"]["lines"]) == 1
    assert body["cart"]["lines"][0]["item_id"] == "everything_bagel"

    r2 = await client.get(api_path(RESTAURANT_ID, call_id, "/cart"))
    assert r2.status_code == 200
    cart_body = r2.json()
    assert cart_body["status"] == "success"
    assert len(cart_body["cart"]["lines"]) == 1


@pytest.mark.asyncio
async def test_unified_tool_dispatch(client: AsyncClient, call_id: str) -> None:
    await _reset(client, call_id)
    base = api_path(RESTAURANT_ID, call_id, "/tool")

    add = await client.post(
        base,
        json={
            "tool": "add_item",
            "arguments": {"item_term": "cream cheese sandwich"},
        },
    )
    assert add.status_code == 200
    line_id = add.json()["line_id"]
    assert line_id

    mod = await client.post(
        base,
        json={
            "tool": "set_modifier",
            "arguments": {
                "line_id": line_id,
                "requested_modifiers": ["tomato"],
            },
        },
    )
    assert mod.status_code == 200
    assert mod.json()["status"] in ("success", "clarification", "violation")

    get = await client.post(base, json={"tool": "get_cart", "arguments": {}})
    assert get.status_code == 200
    assert len(get.json()["cart"]["lines"]) == 1

    rem = await client.post(
        base,
        json={"tool": "remove_item", "arguments": {"line_id": line_id}},
    )
    assert rem.status_code == 200
    assert rem.json()["status"] == "success"
    assert len(rem.json()["cart"]["lines"]) == 0


@pytest.mark.asyncio
async def test_remove_item_and_set_modifier_routes(client: AsyncClient, call_id: str) -> None:
    await _reset(client, call_id)
    add = await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/add_item"),
        json={"item_term": "coffee", "requested_modifiers": ["milk"]},
    )
    line_id = add.json()["line_id"]

    mod = await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/set_modifier"),
        json={"line_id": line_id, "requested_modifiers": ["no sugar"]},
    )
    assert mod.status_code == 200
    assert mod.json()["status"] == "success"

    rem = await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/remove_item"),
        json={"line_id": line_id},
    )
    assert rem.status_code == 200
    assert rem.json()["status"] == "success"
    assert rem.json()["cart"]["lines"] == []


@pytest.mark.asyncio
async def test_checkout_empty_cart(client: AsyncClient, call_id: str) -> None:
    await _reset(client, call_id)
    r = await client.post(
        api_path(RESTAURANT_ID, call_id, "/checkout"),
        json={"customer_phone": "+15551234567"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "violation"


@pytest.mark.asyncio
async def test_check_ambiguity(client: AsyncClient, call_id: str) -> None:
    await _reset(client, call_id)
    r = await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/check_ambiguity"),
        params={"query": "sandwich with eggs"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "clarification"
    assert len(body["options"]) >= 3


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
async def test_scenario_run(client: AsyncClient, scenario_id: str) -> None:
    call_id = f"scenario-{scenario_id}-{uuid.uuid4().hex[:8]}"
    r = await client.post(
        api_path(RESTAURANT_ID, call_id, f"/scenarios/{scenario_id}/run"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("success", "clarification", "violation", "advance_notice")
    assert body["cart"] is not None


@pytest.mark.asyncio
async def test_unknown_tool_returns_400(client: AsyncClient, call_id: str) -> None:
    await _reset(client, call_id)
    r = await client.post(
        api_path(RESTAURANT_ID, call_id, "/tool"),
        json={"tool": "fly_to_moon", "arguments": {}},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB"),
    reason="Set INTEGRATION_DB=1 to run order persistence tests against DATABASE_URL in .env",
)
async def test_order_lookup_by_phone(client: AsyncClient) -> None:
    """Full checkout + lookup + resume flow against a real Postgres instance."""
    from apps.order_api.db.engine import check_database, close_database, init_database

    # Re-load DATABASE_URL from .env for this test only.
    os.environ.pop("DATABASE_URL", None)
    get_settings.cache_clear()
    init_database()

    if not get_settings().database_enabled or not await check_database():
        pytest.skip("DATABASE_URL not configured or database unreachable")

    call_id = f"db-{uuid.uuid4().hex[:8]}"
    phone = "+15559876543"
    await _reset(client, call_id)

    await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/add_item"),
        json={"item_term": "cream cheese sandwich"},
    )
    checkout = await client.post(
        api_path(RESTAURANT_ID, call_id, "/checkout"),
        json={"customer_phone": phone},
    )
    assert checkout.status_code == 200
    checkout_body = checkout.json()
    assert checkout_body["status"] == "success"
    order_id = checkout_body.get("order_id")
    assert order_id

    lookup = await client.get(
        f"/v1/restaurants/{RESTAURANT_ID}/orders/by-phone/{phone.replace('+', '%2B')}"
    )
    assert lookup.status_code == 200
    assert lookup.json()["order_id"] == order_id

    new_call = f"resume-{uuid.uuid4().hex[:8]}"
    resume = await client.post(
        api_path(RESTAURANT_ID, new_call, "/resume-from-phone"),
        json={"customer_phone": phone},
    )
    assert resume.status_code == 200
    assert resume.json()["status"] == "success"
    assert resume.json()["order_id"] == order_id
    assert len(resume.json()["cart"]["lines"]) >= 1

    await close_database()
    os.environ["DATABASE_URL"] = ""
    get_settings.cache_clear()
    init_database()
