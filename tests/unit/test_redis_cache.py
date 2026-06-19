"""Redis session cache tests — requires local Redis (docker compose)."""

from __future__ import annotations

import os

import pytest

from apps.order_api.db import redis_cache
from apps.order_api.settings import get_settings


@pytest.fixture(autouse=True)
async def _redis_test_env():
    os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"
    get_settings.cache_clear()
    await redis_cache.close_redis()
    yield
    await redis_cache.close_redis()
    os.environ["REDIS_URL"] = ""
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_redis_cart_roundtrip() -> None:
    if not await redis_cache.init_redis():
        pytest.skip("Redis not available — run docker compose up")

    rid, cid = "hot_bagels_2nd_street", "redis-test-call"
    payload = {
        "restaurant_id": rid,
        "lines": [
            {
                "line_id": "l1",
                "item_id": "coffee",
                "item_name": "Coffee",
                "quantity": 1,
                "modifier_ids": [],
                "modifier_names": [],
                "special_instructions": "",
                "unit_price_cents": 350,
                "line_total_cents": 350,
            }
        ],
        "total_cents": 350,
    }
    await redis_cache.set_cached_cart(rid, cid, payload)
    loaded = await redis_cache.get_cached_cart(rid, cid)
    assert loaded is not None
    assert loaded["lines"][0]["item_id"] == "coffee"
    await redis_cache.delete_cached_cart(rid, cid)
    assert await redis_cache.get_cached_cart(rid, cid) is None
