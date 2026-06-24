from __future__ import annotations

import re
from datetime import UTC, datetime


def normalize_pan(raw: str) -> str:
    return re.sub(r"\D", "", raw.strip())


def mask_pan(pan: str) -> str:
    digits = normalize_pan(pan)
    if len(digits) < 4:
        return "****"
    return f"**** **** **** {digits[-4:]}"


def luhn_check(pan: str) -> bool:
    digits = normalize_pan(pan)
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    reverse = digits[::-1]
    for index, char in enumerate(reverse):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def validate_expiry(exp_month: int, exp_year: int) -> bool:
    if not 1 <= exp_month <= 12:
        return False
    now = datetime.now(UTC)
    year = exp_year if exp_year >= 100 else 2000 + exp_year
    if year < now.year:
        return False
    if year == now.year and exp_month < now.month:
        return False
    return True


def validate_cvv(cvv: str) -> bool:
    digits = normalize_pan(cvv)
    return len(digits) in (3, 4) and digits.isdigit()


def is_declined_test_pan(pan: str) -> bool:
    """Simulate processor decline for test cards ending in 0002."""
    digits = normalize_pan(pan)
    return digits.endswith("0002")
