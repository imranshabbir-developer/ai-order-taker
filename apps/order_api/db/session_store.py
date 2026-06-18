from __future__ import annotations

from order_engine.models import Cart
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from apps.order_api.db.engine import database_configured, get_db_session
from apps.order_api.db.models import CallSessionRow, RestaurantRow


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

    async def load_cart(self, restaurant_id: str, call_id: str) -> Cart | None:
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
            return Cart.model_validate(row.cart_json)

    async def save_cart(self, restaurant_id: str, call_id: str, cart: Cart) -> None:
        if not database_configured():
            return
        payload = cart.model_dump(mode="json")
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
