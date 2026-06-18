from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AddItemRequest(BaseModel):
    item_term: str = ""
    requested_modifiers: list[str] = Field(default_factory=list)
    quantity: int = 1
    special_instructions: str = ""
    item_id: str | None = None


class RemoveItemRequest(BaseModel):
    line_id: str


class SetModifierRequest(BaseModel):
    line_id: str
    requested_modifiers: list[str] = Field(default_factory=list)


class CheckoutRequest(BaseModel):
    customer_phone: str = ""


class ResumeOrderRequest(BaseModel):
    customer_phone: str = ""
    order_id: str | None = None


class ToolInvokeRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel):
    status: str
    message: str
    line_id: str | None = None
    options: list[str] = Field(default_factory=list)
    cart: dict | None = None
    spoken_summary: str | None = None
    sms_summary: str | None = None
    order_id: str | None = None


class OrderSummaryResponse(BaseModel):
    order_id: str
    restaurant_id: str
    call_id: str
    customer_phone: str | None
    status: str
    cart: dict
    spoken_summary: str | None = None
    sms_summary: str | None = None
