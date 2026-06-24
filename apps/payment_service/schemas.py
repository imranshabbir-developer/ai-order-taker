from __future__ import annotations

from pydantic import BaseModel, Field


class ChargeRequest(BaseModel):
    order_id: str
    amount_cents: int = Field(gt=0)
    card_number: str
    exp_month: int = Field(ge=1, le=12)
    exp_year: int = Field(ge=0, le=9999)
    cvv: str
    call_id: str = ""


class ChargeResponse(BaseModel):
    status: str
    message: str
    charge_id: str | None = None
    order_id: str
    amount_cents: int
    last_four: str | None = None
    token: str | None = None
