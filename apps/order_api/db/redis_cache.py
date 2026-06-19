"""Optional Redis cache for active call session carts (Sprint 2.4)."""

from __future__ import annotations

import json
from typing import Any

from apps.order_api.settings import get_settings

_redis_client: Any | None = None
_redis_checked = False
_redis_available = False

SESSION_TTL_SECONDS = 3600


async def init_redis() -> bool:
    global _redis_client, _redis_checked, _redis_available
    if _redis_checked:
        return _redis_available
    _redis_checked = True
    url = get_settings().redis_url.strip()
    if not url:
        return False
    try:
        from redis.asyncio import Redis
    except ImportError:
        return False
    try:
        client = Redis.from_url(url, decode_responses=True)
        await client.ping()
        _redis_client = client
        _redis_available = True
    except Exception:
        _redis_client = None
        _redis_available = False
    return _redis_available


async def close_redis() -> None:
    global _redis_client, _redis_checked, _redis_available
    if _redis_client is not None:
        await _redis_client.aclose()
    _redis_client = None
    _redis_checked = False
    _redis_available = False


def redis_configured() -> bool:
    return bool(get_settings().redis_url.strip())


async def check_redis() -> bool:
    if not await init_redis():
        return False
    try:
        assert _redis_client is not None
        await _redis_client.ping()
        return True
    except Exception:
        return False


def _key(restaurant_id: str, call_id: str) -> str:
    return f"call:{restaurant_id}:{call_id}:cart"


async def get_cached_cart(restaurant_id: str, call_id: str) -> dict[str, Any] | None:
    if not await init_redis() or _redis_client is None:
        return None
    raw = await _redis_client.get(_key(restaurant_id, call_id))
    if not raw:
        return None
    return json.loads(raw)


async def set_cached_cart(restaurant_id: str, call_id: str, cart_json: dict[str, Any]) -> None:
    if not await init_redis() or _redis_client is None:
        return
    await _redis_client.set(
        _key(restaurant_id, call_id),
        json.dumps(cart_json),
        ex=SESSION_TTL_SECONDS,
    )


async def delete_cached_cart(restaurant_id: str, call_id: str) -> None:
    if not await init_redis() or _redis_client is None:
        return
    await _redis_client.delete(_key(restaurant_id, call_id))
