from __future__ import annotations

from apps.payment_service.card import (
    is_declined_test_pan,
    luhn_check,
    mask_pan,
    validate_cvv,
    validate_expiry,
)
from apps.payment_service.processor import PaymentProcessor
from apps.payment_service.schemas import ChargeRequest


def test_luhn_valid_visa() -> None:
    assert luhn_check("4111111111111111")


def test_luhn_rejects_invalid() -> None:
    assert not luhn_check("4111111111111112")


def test_mask_pan() -> None:
    assert mask_pan("4111111111111111") == "**** **** **** 1111"


def test_validate_expiry() -> None:
    assert validate_expiry(12, 2030)
    assert not validate_expiry(1, 2020)


def test_validate_cvv() -> None:
    assert validate_cvv("123")
    assert not validate_cvv("12")


def test_processor_charge_success() -> None:
    processor = PaymentProcessor()
    result = processor.charge(
        ChargeRequest(
            order_id="order-1",
            amount_cents=1250,
            card_number="4111111111111111",
            exp_month=12,
            exp_year=2030,
            cvv="123",
        )
    )
    assert result.status == "succeeded"
    assert result.last_four == "1111"
    assert result.charge_id


def test_processor_declines_test_card() -> None:
    assert is_declined_test_pan("4000000000000002")
    processor = PaymentProcessor()
    result = processor.charge(
        ChargeRequest(
            order_id="order-2",
            amount_cents=500,
            card_number="4000000000000002",
            exp_month=12,
            exp_year=2030,
            cvv="123",
        )
    )
    assert result.status == "declined"
