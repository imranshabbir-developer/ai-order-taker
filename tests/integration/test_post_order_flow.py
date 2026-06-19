from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from apps.payment_service.processor import default_processor
from apps.sms_gateway.sender import default_sender
from tests.integration.conftest import RESTAURANT_ID, api_path


@pytest.mark.asyncio
async def test_store_status(client: AsyncClient) -> None:
    r = await client.get(f"/v1/restaurants/{RESTAURANT_ID}/store-status")
    assert r.status_code == 200
    body = r.json()
    assert "is_open" in body
    assert "delivery_available" in body
    assert body.get("escalation_phone")


@pytest.mark.asyncio
async def test_checkout_sends_sms_and_payment(client: AsyncClient) -> None:
    default_sender.messages.clear()
    default_processor.charges.clear()
    call_id = f"pay-{uuid.uuid4().hex[:8]}"
    phone = "+15551112222"

    await client.post(api_path(RESTAURANT_ID, call_id, "/reset"))
    await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/add_item"),
        json={"item_term": "cream cheese sandwich"},
    )
    checkout = await client.post(
        api_path(RESTAURANT_ID, call_id, "/checkout"),
        json={"customer_phone": phone},
    )
    assert checkout.status_code == 200
    body = checkout.json()
    assert body["status"] == "success"
    assert body["order_id"]
    assert body["sms_sent"] is True
    assert body["payment_required"] is True
    assert body["spoken_summary"] == body["sms_summary"]
    assert len(default_sender.messages) >= 1

    order_id = body["order_id"]
    amount = body["cart"]["total_cents"]
    pay = await client.post(
        f"/v1/restaurants/{RESTAURANT_ID}/orders/{order_id}/payment",
        json={
            "card_number": "4111111111111111",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "123",
        },
    )
    assert pay.status_code == 200
    pay_body = pay.json()
    assert pay_body["status"] == "succeeded"
    assert pay_body["amount_cents"] == amount
    assert pay_body["last_four"] == "1111"


@pytest.mark.asyncio
async def test_payment_parity_with_cart_total(client: AsyncClient) -> None:
    default_processor.charges.clear()
    call_id = f"parity-{uuid.uuid4().hex[:8]}"
    await client.post(api_path(RESTAURANT_ID, call_id, "/reset"))
    await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/add_item"),
        json={"item_term": "coffee", "requested_modifiers": ["no sugar"]},
    )
    cart = await client.get(api_path(RESTAURANT_ID, call_id, "/cart"))
    total = cart.json()["cart"]["total_cents"]
    spoken = cart.json()["spoken_summary"]
    sms = cart.json()["sms_summary"]
    assert spoken == sms

    checkout = await client.post(
        api_path(RESTAURANT_ID, call_id, "/checkout"),
        json={"customer_phone": "+15553334444"},
    )
    order_id = checkout.json()["order_id"]
    pay = await client.post(
        f"/v1/restaurants/{RESTAURANT_ID}/orders/{order_id}/payment",
        json={
            "card_number": "4111111111111111",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "123",
        },
    )
    assert pay.json()["amount_cents"] == total


@pytest.mark.asyncio
async def test_list_restaurants_includes_demo_cafe(client: AsyncClient) -> None:
    r = await client.get("/v1/restaurants")
    ids = {item["id"] for item in r.json()["restaurants"]}
    assert "hot_bagels_2nd_street" in ids
    assert "demo_cafe" in ids


@pytest.mark.asyncio
async def test_escalation_returns_staff_phone(client: AsyncClient) -> None:
    call_id = f"esc-{uuid.uuid4().hex[:8]}"
    r = await client.post(
        f"/v1/restaurants/{RESTAURANT_ID}/calls/{call_id}/escalate",
        json={"reason": "customer_requested"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "escalating"
    assert body["transfer_to"]
    assert body["call_id"] == call_id
