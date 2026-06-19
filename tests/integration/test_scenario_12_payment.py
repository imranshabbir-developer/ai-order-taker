"""Scenario 12 — checkout + isolated payment capture (Sprint 6)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.integration.conftest import RESTAURANT_ID, api_path


@pytest.mark.asyncio
async def test_scenario_12_payment_after_checkout(client: AsyncClient) -> None:
    call_id = f"sc12-{uuid.uuid4().hex[:8]}"
    phone = "+15551234012"

    await client.post(api_path(RESTAURANT_ID, call_id, "/reset"))
    add = await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/add_item"),
        json={"item_term": "cream cheese sandwich"},
    )
    assert add.json()["status"] == "success"

    cart = await client.get(api_path(RESTAURANT_ID, call_id, "/cart"))
    total = cart.json()["cart"]["total_cents"]
    spoken = cart.json()["spoken_summary"]
    assert spoken == cart.json()["sms_summary"]

    checkout = await client.post(
        api_path(RESTAURANT_ID, call_id, "/checkout"),
        json={"customer_phone": phone},
    )
    body = checkout.json()
    assert body["status"] == "success"
    assert body["payment_required"] is True
    order_id = body["order_id"]

    pay = await client.post(
        f"/v1/restaurants/{RESTAURANT_ID}/orders/{order_id}/payment",
        json={
            "card_number": "4111111111111111",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "123",
        },
        params={"call_id": call_id},
    )
    pay_body = pay.json()
    assert pay_body["status"] == "succeeded"
    assert pay_body["amount_cents"] == total
    assert pay_body["last_four"] == "1111"
