from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _resolve_tz(tz_name: str) -> timezone | ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        # Windows without tzdata — approximate US Eastern for MVP store-hours checks.
        return timezone(timedelta(hours=-5))


def _parse_time(value: str) -> tuple[int, int] | None:
    if value.lower() == "closed":
        return None
    hour, minute = value.split(":")
    return int(hour), int(minute)


def is_store_open(operations: dict[str, Any], *, now: datetime | None = None) -> tuple[bool, str]:
    """Return (open, message) using restaurant operations config."""
    tz_name = operations.get("timezone", "America/New_York")
    tz = _resolve_tz(tz_name)
    current = (now or datetime.now(UTC)).astimezone(tz)
    weekday = current.strftime("%A").lower()
    hours = operations.get("store_hours", {}).get(weekday, {})
    open_raw = str(hours.get("open", "closed"))
    close_raw = str(hours.get("close", "closed"))

    closed_msg = operations.get("agent_prompts_and_messages", {}).get(
        "closed_store_message",
        "We are currently closed. Please call back during business hours.",
    )

    open_time = _parse_time(open_raw)
    close_time = _parse_time(close_raw)
    if open_time is None or close_time is None:
        return False, closed_msg

    current_minutes = current.hour * 60 + current.minute
    open_minutes = open_time[0] * 60 + open_time[1]
    close_minutes = close_time[0] * 60 + close_time[1]
    if open_minutes <= current_minutes < close_minutes:
        return True, "Store is open."
    return False, closed_msg


def delivery_available(operations: dict[str, Any]) -> tuple[bool, str]:
    delivery = operations.get("ordering_modes", {}).get("delivery", {})
    if not delivery.get("enabled", True):
        msg = operations.get("agent_prompts_and_messages", {}).get(
            "delivery_cutoff_message",
            "Delivery is not available right now.",
        )
        return False, msg
    return True, "Delivery is available."
