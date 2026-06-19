from __future__ import annotations

from apps.sms_gateway.schemas import SendSmsRequest
from apps.sms_gateway.sender import SmsSender, mask_phone


def test_mask_phone() -> None:
    assert mask_phone("+15551234567").endswith("4567")


def test_send_sms_success() -> None:
    sender = SmsSender()
    result = sender.send(
        SendSmsRequest(
            order_id="abc",
            to_phone="+15551234567",
            body="Your order: 1 cream cheese sandwich. Total $8.50",
            restaurant_id="hot_bagels_2nd_street",
        )
    )
    assert result.status == "sent"
    assert result.sms_id
    assert len(sender.messages) == 1


def test_send_sms_requires_phone() -> None:
    sender = SmsSender()
    result = sender.send(
        SendSmsRequest(order_id="abc", to_phone="", body="Hello", restaurant_id="demo")
    )
    assert result.status == "failed"
