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
    sms_sent: bool | None = None
    payment_required: bool | None = None


class OrderSummaryResponse(BaseModel):
    order_id: str
    restaurant_id: str
    call_id: str
    customer_phone: str | None
    status: str
    cart: dict
    spoken_summary: str | None = None
    sms_summary: str | None = None


class PaymentCaptureRequest(BaseModel):
    card_number: str
    exp_month: int = Field(ge=1, le=12)
    exp_year: int = Field(ge=0, le=9999)
    cvv: str


class PaymentCaptureResponse(BaseModel):
    status: str
    message: str
    order_id: str
    amount_cents: int
    last_four: str | None = None
    charge_id: str | None = None


class StoreStatusResponse(BaseModel):
    is_open: bool
    message: str
    delivery_available: bool
    delivery_message: str
    escalation_phone: str | None = None


class CallStartRequest(BaseModel):
    caller_phone: str = ""


class CallStartResponse(BaseModel):
    call_id: str
    restaurant_id: str
    is_open: bool
    message: str
    delivery_available: bool
    delivery_message: str
    escalation_phone: str | None = None


class EscalationRequest(BaseModel):
    reason: str = "customer_requested"


class EscalationResponse(BaseModel):
    status: str
    call_id: str
    reason: str
    transfer_to: str
    message: str
