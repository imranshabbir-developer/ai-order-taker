from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apps.order_api.store_hours import delivery_available, is_store_open


def _eastern() -> timezone:
    try:
        return ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=-5))


def test_saturday_closed() -> None:
    ops = {
        "timezone": "America/New_York",
        "store_hours": {
            "saturday": {"open": "closed", "close": "closed"},
        },
        "agent_prompts_and_messages": {"closed_store_message": "We are closed."},
    }
    saturday_noon = datetime(2026, 6, 20, 12, 0, tzinfo=_eastern())
    open_now, msg = is_store_open(ops, now=saturday_noon)
    assert open_now is False
    assert msg == "We are closed."


def test_delivery_enabled() -> None:
    ops = {"ordering_modes": {"delivery": {"enabled": True}}}
    ok, _ = delivery_available(ops)
    assert ok is True
