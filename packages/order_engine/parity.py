from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParityReport:
    """Sprint 6.7 — spoken, SMS, and payment totals must agree."""

    spoken_matches_sms: bool
    payment_matches_cart: bool | None
    total_cents: int
    payment_cents: int | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        if not self.spoken_matches_sms:
            return False
        if self.payment_matches_cart is False:
            return False
        return True


def check_order_parity(
    *,
    spoken_summary: str,
    sms_summary: str,
    total_cents: int,
    payment_cents: int | None = None,
) -> ParityReport:
    errors: list[str] = []
    spoken_ok = spoken_summary == sms_summary
    if not spoken_ok:
        errors.append("spoken_summary != sms_summary")

    payment_ok: bool | None = None
    if payment_cents is not None:
        payment_ok = payment_cents == total_cents
        if not payment_ok:
            errors.append(f"payment_cents ({payment_cents}) != cart total_cents ({total_cents})")

    return ParityReport(
        spoken_matches_sms=spoken_ok,
        payment_matches_cart=payment_ok,
        total_cents=total_cents,
        payment_cents=payment_cents,
        errors=errors,
    )
