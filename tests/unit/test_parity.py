from __future__ import annotations

from order_engine.parity import check_order_parity


def test_spoken_sms_match() -> None:
    report = check_order_parity(
        spoken_summary="Coffee — $3.50",
        sms_summary="Coffee — $3.50",
        total_cents=350,
    )
    assert report.ok
    assert report.spoken_matches_sms
    assert report.payment_matches_cart is None


def test_spoken_sms_mismatch() -> None:
    report = check_order_parity(
        spoken_summary="Coffee — $3.50",
        sms_summary="Coffee $3.50",
        total_cents=350,
    )
    assert not report.ok
    assert "spoken_summary != sms_summary" in report.errors[0]


def test_payment_matches_cart() -> None:
    report = check_order_parity(
        spoken_summary="Total $7.50",
        sms_summary="Total $7.50",
        total_cents=750,
        payment_cents=750,
    )
    assert report.ok
    assert report.payment_matches_cart is True


def test_payment_mismatch() -> None:
    report = check_order_parity(
        spoken_summary="Total $7.50",
        sms_summary="Total $7.50",
        total_cents=750,
        payment_cents=500,
    )
    assert not report.ok
    assert any("payment_cents" in e for e in report.errors)
