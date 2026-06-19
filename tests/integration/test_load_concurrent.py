from __future__ import annotations

import asyncio
import uuid

import pytest
from httpx import AsyncClient

from tests.integration.conftest import RESTAURANT_ID, api_path


async def _simulate_call(client: AsyncClient, index: int) -> bool:
    call_id = f"load-{index}-{uuid.uuid4().hex[:8]}"
    await client.post(api_path(RESTAURANT_ID, call_id, "/reset"))
    add = await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/add_item"),
        json={"item_term": "coffee", "requested_modifiers": ["no sugar"]},
    )
    if add.status_code != 200 or add.json().get("status") != "success":
        return False
    cart = await client.get(api_path(RESTAURANT_ID, call_id, "/cart"))
    return cart.status_code == 200 and cart.json().get("cart", {}).get("lines")


@pytest.mark.asyncio
async def test_five_concurrent_calls(client: AsyncClient) -> None:
    """Sprint 7.3 — five parallel sessions must not interfere."""
    results = await asyncio.gather(*[_simulate_call(client, i) for i in range(5)])
    assert all(results), f"Some concurrent calls failed: {results}"
