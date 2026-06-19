from __future__ import annotations

from pydantic import BaseModel


class SendSmsRequest(BaseModel):
    order_id: str
    to_phone: str
    body: str
    restaurant_id: str = ""


class SendSmsResponse(BaseModel):
    status: str
    message: str
    sms_id: str | None = None
    order_id: str
    to_phone: str
    body_preview: str = ""
