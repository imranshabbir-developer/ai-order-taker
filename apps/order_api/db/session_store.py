from __future__ import annotations

from order_engine.models import Cart
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from apps.order_api.db import redis_cache
from apps.order_api.db.engine import database_configured, get_db_session
from apps.order_api.db.models import CallSessionRow, RestaurantRow
from apps.order_api.db.order_store import normalize_phone


class SessionStore:
    """Persist active call carts in PostgreSQL."""

    async def ensure_restaurant(self, restaurant_id: str, name: str) -> None:
        if not database_configured():
            return
        async with get_db_session() as session:
            stmt = (
                insert(RestaurantRow)
                .values(id=restaurant_id, name=name)
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(stmt)
            await session.commit()

    async def get_caller_phone(self, restaurant_id: str, call_id: str) -> str | None:
        if not database_configured():
            return None
        async with get_db_session() as session:
            result = await session.execute(
                select(CallSessionRow.caller_phone).where(
                    CallSessionRow.restaurant_id == restaurant_id,
                    CallSessionRow.call_id == call_id,
                )
            )
            return result.scalar_one_or_none()

    async def set_caller_phone(self, restaurant_id: str, call_id: str, caller_phone: str) -> None:
        if not database_configured():
            return
        phone = normalize_phone(caller_phone)
        async with get_db_session() as session:
            result = await session.execute(
                select(CallSessionRow).where(
                    CallSessionRow.restaurant_id == restaurant_id,
                    CallSessionRow.call_id == call_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                stmt = (
                    insert(CallSessionRow)
                    .values(
                        restaurant_id=restaurant_id,
                        call_id=call_id,
                        caller_phone=phone,
                        cart_json={"restaurant_id": restaurant_id, "lines": []},
                    )
                    .on_conflict_do_update(
                        constraint="uq_call_session",
                        set_={"caller_phone": phone},
                    )
                )
                await session.execute(stmt)
            else:
                row.caller_phone = phone
            await session.commit()

    async def load_cart(self, restaurant_id: str, call_id: str) -> Cart | None:
        cached = await redis_cache.get_cached_cart(restaurant_id, call_id)
        if cached and cached.get("lines"):
            return Cart.model_validate(cached)
        if not database_configured():
            return None
        async with get_db_session() as session:
            result = await session.execute(
                select(CallSessionRow).where(
                    CallSessionRow.restaurant_id == restaurant_id,
                    CallSessionRow.call_id == call_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            if not row.cart_json or not row.cart_json.get("lines"):
                return None
            cart = Cart.model_validate(row.cart_json)
            await redis_cache.set_cached_cart(restaurant_id, call_id, row.cart_json)
            return cart

    async def save_cart(self, restaurant_id: str, call_id: str, cart: Cart) -> None:
        payload = cart.model_dump(mode="json")
        await redis_cache.set_cached_cart(restaurant_id, call_id, payload)
        if not database_configured():
            return
        async with get_db_session() as session:
            stmt = (
                insert(CallSessionRow)
                .values(
                    restaurant_id=restaurant_id,
                    call_id=call_id,
                    cart_json=payload,
                )
                .on_conflict_do_update(
                    constraint="uq_call_session",
                    set_={"cart_json": payload},
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def delete_session(self, restaurant_id: str, call_id: str) -> None:
        await redis_cache.delete_cached_cart(restaurant_id, call_id)
        if not database_configured():
            return
        async with get_db_session() as session:
            result = await session.execute(
                select(CallSessionRow).where(
                    CallSessionRow.restaurant_id == restaurant_id,
                    CallSessionRow.call_id == call_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is not None:
                await session.delete(row)
                await session.commit()
