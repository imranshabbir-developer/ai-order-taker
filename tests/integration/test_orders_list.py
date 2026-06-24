from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.integration.conftest import RESTAURANT_ID, api_path


@pytest.mark.asyncio
async def test_list_orders_today(client: AsyncClient) -> None:
    call_id = f"ord-list-{uuid.uuid4().hex[:8]}"
    await client.post(api_path(RESTAURANT_ID, call_id, "/reset"))
    await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/add_item"),
        json={"item_term": "cream cheese sandwich"},
    )
    checkout = await client.post(
        api_path(RESTAURANT_ID, call_id, "/checkout"),
        json={"customer_phone": "+15551234001"},
    )
    assert checkout.status_code == 200
    order_id = checkout.json()["order_id"]
    assert order_id

    listed = await client.get(f"/v1/restaurants/{RESTAURANT_ID}/orders?day=today")
    assert listed.status_code == 200
    body = listed.json()
    assert body["count"] >= 1
    ids = {o["order_id"] for o in body["orders"]}
    assert order_id in ids

    detail = await client.get(f"/v1/restaurants/{RESTAURANT_ID}/orders/{order_id}")
    assert detail.status_code == 200
    d = detail.json()
    assert d["call_id"] == call_id
    assert d["total_cents"] == d["cart"]["total_cents"]
