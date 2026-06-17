from __future__ import annotations

from pydantic import BaseModel, Field

from order_engine.models import Cart, OrderResultStatus


class AddItemResult(BaseModel):
    status: OrderResultStatus
    message: str
    line_id: str | None = None
    options: list[str] = Field(default_factory=list)
    cart: Cart | None = None


class OperationResult(BaseModel):
    status: OrderResultStatus
    message: str
    cart: Cart | None = None
    options: list[str] = Field(default_factory=list)
