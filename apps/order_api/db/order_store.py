from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from order_engine.models import Cart
from sqlalchemy import select, update

from apps.order_api.db.engine import database_configured, get_db_session
from apps.order_api.db.models import OrderRow
from apps.order_api.store_hours import _resolve_tz


@dataclass
class OrderRecord:
    id: uuid.UUID
    restaurant_id: str
    call_id: str
    customer_phone: str | None
    status: str
    cart: Cart
    spoken_summary: str | None
    sms_summary: str | None
    created_at: datetime | None = None


class OrderStore:
    """Persist completed and in-progress orders."""

    async def create_order(
        self,
        restaurant_id: str,
        call_id: str,
        cart: Cart,
        spoken_summary: str,
        sms_summary: str,
        customer_phone: str | None = None,
        status: str = "open",
    ) -> OrderRecord | None:
        if not database_configured():
            return None
        payload = cart.model_dump(mode="json")
        order_id = uuid.uuid4()
        normalized_phone = normalize_phone(customer_phone) if customer_phone else None
        if not normalized_phone and cart.customer_phone:
            normalized_phone = normalize_phone(cart.customer_phone)
        async with get_db_session() as session:
            row = OrderRow(
                id=order_id,
                restaurant_id=restaurant_id,
                call_id=call_id,
                customer_phone=normalized_phone,
                status=status,
                cart_json=payload,
                spoken_summary=spoken_summary,
                sms_summary=sms_summary,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_record(row)

    async def update_order(
        self,
        order_id: uuid.UUID,
        cart: Cart,
        spoken_summary: str,
        sms_summary: str,
    ) -> OrderRecord | None:
        if not database_configured():
            return None
        payload = cart.model_dump(mode="json")
        async with get_db_session() as session:
            await session.execute(
                update(OrderRow)
                .where(OrderRow.id == order_id)
                .values(
                    cart_json=payload,
                    spoken_summary=spoken_summary,
                    sms_summary=sms_summary,
                )
            )
            await session.commit()
            result = await session.execute(select(OrderRow).where(OrderRow.id == order_id))
            row = result.scalar_one_or_none()
            return _to_record(row) if row else None

    async def get_order(self, order_id: uuid.UUID) -> OrderRecord | None:
        if not database_configured():
            return None
        async with get_db_session() as session:
            result = await session.execute(select(OrderRow).where(OrderRow.id == order_id))
            row = result.scalar_one_or_none()
            return _to_record(row) if row else None

    async def update_status(self, order_id: uuid.UUID, status: str) -> OrderRecord | None:
        if not database_configured():
            return None
        async with get_db_session() as session:
            await session.execute(
                update(OrderRow).where(OrderRow.id == order_id).values(status=status)
            )
            await session.commit()
            result = await session.execute(select(OrderRow).where(OrderRow.id == order_id))
            row = result.scalar_one_or_none()
            return _to_record(row) if row else None

    async def find_latest_open_by_phone(
        self,
        restaurant_id: str,
        customer_phone: str,
    ) -> OrderRecord | None:
        if not database_configured():
            return None
        normalized = _normalize_phone(customer_phone)
        async with get_db_session() as session:
            result = await session.execute(
                select(OrderRow)
                .where(
                    OrderRow.restaurant_id == restaurant_id,
                    OrderRow.status == "open",
                    OrderRow.customer_phone == normalized,
                )
                .order_by(OrderRow.updated_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return _to_record(row) if row else None

    async def list_orders(
        self,
        restaurant_id: str,
        *,
        day: str = "today",
        limit: int = 100,
        timezone_name: str = "America/New_York",
    ) -> list[OrderRecord]:
        if not database_configured():
            return []
        start_utc, end_utc = _day_bounds_utc(day, timezone_name)
        async with get_db_session() as session:
            result = await session.execute(
                select(OrderRow)
                .where(
                    OrderRow.restaurant_id == restaurant_id,
                    OrderRow.created_at >= start_utc,
                    OrderRow.created_at < end_utc,
                )
                .order_by(OrderRow.created_at.desc())
                .limit(limit)
            )
            return [_to_record(row) for row in result.scalars().all()]


def _day_bounds_utc(day: str, timezone_name: str) -> tuple[datetime, datetime]:
    tz = _resolve_tz(timezone_name)
    now_local = datetime.now(UTC).astimezone(tz)
    if day == "tomorrow":
        start_local = (now_local + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_local = start_local + timedelta(days=1)
    elif day == "all":
        end_local = (now_local + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start_local = end_local - timedelta(days=30)
    else:
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def normalize_phone(phone: str) -> str:
    return "".join(ch for ch in phone.strip() if ch.isdigit() or ch == "+")


def _normalize_phone(phone: str) -> str:
    return normalize_phone(phone)


def _to_record(row: OrderRow) -> OrderRecord:
    return OrderRecord(
        id=row.id,
        restaurant_id=row.restaurant_id,
        call_id=row.call_id,
        customer_phone=row.customer_phone,
        status=row.status,
        cart=Cart.model_validate(row.cart_json),
        spoken_summary=row.spoken_summary,
        sms_summary=row.sms_summary,
        created_at=row.created_at,
    )
