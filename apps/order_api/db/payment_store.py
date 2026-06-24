"""Payment charge persistence — stores token + last_four only, never raw PAN."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from apps.order_api.db.engine import database_configured, get_db_session
from apps.order_api.db.models import PaymentChargeRow


@dataclass
class PaymentChargeRecord:
    id: uuid.UUID
    order_id: uuid.UUID
    charge_id: str
    amount_cents: int
    last_four: str | None
    token: str | None
    status: str
    call_id: str | None
    created_at: datetime | None = None


class PaymentStore:
    async def save_charge(
        self,
        *,
        order_id: uuid.UUID,
        charge_id: str,
        amount_cents: int,
        last_four: str | None,
        token: str | None,
        status: str,
        call_id: str = "",
    ) -> PaymentChargeRecord | None:
        if not database_configured():
            return None
        row_id = uuid.uuid4()
        async with get_db_session() as session:
            row = PaymentChargeRow(
                id=row_id,
                order_id=order_id,
                charge_id=charge_id,
                amount_cents=amount_cents,
                last_four=last_four,
                token=token,
                status=status,
                call_id=call_id or None,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return _to_record(row)

    async def list_for_order(self, order_id: uuid.UUID) -> list[PaymentChargeRecord]:
        if not database_configured():
            return []
        async with get_db_session() as session:
            result = await session.execute(
                select(PaymentChargeRow)
                .where(PaymentChargeRow.order_id == order_id)
                .order_by(PaymentChargeRow.created_at.desc())
            )
            return [_to_record(row) for row in result.scalars().all()]


def _to_record(row: PaymentChargeRow) -> PaymentChargeRecord:
    return PaymentChargeRecord(
        id=row.id,
        order_id=row.order_id,
        charge_id=row.charge_id,
        amount_cents=row.amount_cents,
        last_four=row.last_four,
        token=row.token,
        status=row.status,
        call_id=row.call_id,
        created_at=row.created_at,
    )
