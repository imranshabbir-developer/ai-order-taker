"""SMS message persistence for order confirmations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from apps.order_api.db.engine import database_configured, get_db_session
from apps.order_api.db.models import SmsMessageRow


@dataclass
class SmsRecord:
    id: uuid.UUID
    order_id: uuid.UUID | None
    sms_id: str
    restaurant_id: str
    to_phone: str
    body: str
    status: str
    created_at: datetime | None = None


class SmsStore:
    async def save_message(
        self,
        *,
        order_id: uuid.UUID | None,
        sms_id: str,
        restaurant_id: str,
        to_phone: str,
        body: str,
        status: str,
    ) -> SmsRecord | None:
        if not database_configured():
            return None
        row_id = uuid.uuid4()
        async with get_db_session() as session:
            row = SmsMessageRow(
                id=row_id,
                order_id=order_id,
                sms_id=sms_id,
                restaurant_id=restaurant_id,
                to_phone=to_phone,
                body=body,
                status=status,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_record(row)

    async def list_for_order(self, order_id: uuid.UUID) -> list[SmsRecord]:
        if not database_configured():
            return []
        async with get_db_session() as session:
            result = await session.execute(
                select(SmsMessageRow)
                .where(SmsMessageRow.order_id == order_id)
                .order_by(SmsMessageRow.created_at.desc())
            )
            return [_to_record(row) for row in result.scalars().all()]


def _to_record(row: SmsMessageRow) -> SmsRecord:
    return SmsRecord(
        id=row.id,
        order_id=row.order_id,
        sms_id=row.sms_id,
        restaurant_id=row.restaurant_id,
        to_phone=row.to_phone,
        body=row.body,
        status=row.status,
        created_at=row.created_at,
    )
