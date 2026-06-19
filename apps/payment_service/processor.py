from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from apps.payment_service.card import (
    is_declined_test_pan,
    luhn_check,
    normalize_pan,
    validate_cvv,
    validate_expiry,
)
from apps.payment_service.schemas import ChargeRequest, ChargeResponse


@dataclass
class ChargeRecord:
    charge_id: str
    order_id: str
    amount_cents: int
    last_four: str
    token: str
    status: str
    call_id: str = ""


@dataclass
class PaymentProcessor:
    """Mock vault — Luhn validation + tokenization; no raw PAN retained."""

    charges: dict[str, ChargeRecord] = field(default_factory=dict)

    def charge(self, request: ChargeRequest) -> ChargeResponse:
        pan = normalize_pan(request.card_number)
        if not luhn_check(pan):
            return ChargeResponse(
                status="declined",
                message="Invalid card number.",
                order_id=request.order_id,
                amount_cents=request.amount_cents,
            )
        if not validate_expiry(request.exp_month, request.exp_year):
            return ChargeResponse(
                status="declined",
                message="Card is expired.",
                order_id=request.order_id,
                amount_cents=request.amount_cents,
            )
        if not validate_cvv(request.cvv):
            return ChargeResponse(
                status="declined",
                message="Invalid security code.",
                order_id=request.order_id,
                amount_cents=request.amount_cents,
            )
        if is_declined_test_pan(pan):
            return ChargeResponse(
                status="declined",
                message="Payment declined by processor.",
                order_id=request.order_id,
                amount_cents=request.amount_cents,
                last_four=pan[-4:],
            )

        charge_id = f"ch_{uuid.uuid4().hex[:12]}"
        token = f"tok_{uuid.uuid4().hex[:16]}"
        last_four = pan[-4:]
        record = ChargeRecord(
            charge_id=charge_id,
            order_id=request.order_id,
            amount_cents=request.amount_cents,
            last_four=last_four,
            token=token,
            status="succeeded",
            call_id=request.call_id,
        )
        self.charges[charge_id] = record
        return ChargeResponse(
            status="succeeded",
            message=f"Payment approved for card ending in {last_four}.",
            charge_id=charge_id,
            order_id=request.order_id,
            amount_cents=request.amount_cents,
            last_four=last_four,
            token=token,
        )


# Shared in-process instance for local/dev when HTTP service is not running.
default_processor = PaymentProcessor()
