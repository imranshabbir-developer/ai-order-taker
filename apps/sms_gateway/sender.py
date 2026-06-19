from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from apps.sms_gateway.schemas import SendSmsRequest, SendSmsResponse


def normalize_phone(phone: str) -> str:
    return "".join(ch for ch in phone.strip() if ch.isdigit() or ch == "+")


def mask_phone(phone: str) -> str:
    digits = normalize_phone(phone)
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"


@dataclass
class SmsRecord:
    sms_id: str
    order_id: str
    to_phone: str
    body: str
    restaurant_id: str
    status: str


@dataclass
class SmsSender:
    """MVP mock — logs messages in memory; swap for Twilio/Kannel in production."""

    messages: dict[str, SmsRecord] = field(default_factory=dict)

    def send(self, request: SendSmsRequest) -> SendSmsResponse:
        phone = normalize_phone(request.to_phone)
        if not phone:
            return SendSmsResponse(
                status="failed",
                message="Missing destination phone number.",
                order_id=request.order_id,
                to_phone=request.to_phone,
            )
        if not request.body.strip():
            return SendSmsResponse(
                status="failed",
                message="SMS body is empty.",
                order_id=request.order_id,
                to_phone=phone,
            )

        sms_id = f"sms_{uuid.uuid4().hex[:12]}"
        record = SmsRecord(
            sms_id=sms_id,
            order_id=request.order_id,
            to_phone=phone,
            body=request.body,
            restaurant_id=request.restaurant_id,
            status="sent",
        )
        self.messages[sms_id] = record
        preview = request.body[:120] + ("..." if len(request.body) > 120 else "")
        return SendSmsResponse(
            status="sent",
            message=f"SMS queued to {mask_phone(phone)}.",
            sms_id=sms_id,
            order_id=request.order_id,
            to_phone=phone,
            body_preview=preview,
        )


default_sender = SmsSender()
