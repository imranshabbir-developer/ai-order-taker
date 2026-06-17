from __future__ import annotations

from order_engine.models import Cart, LineItem


def compute_line_pricing(
    base_price_cents: int,
    modifier_prices: list[int],
    quantity: int,
) -> tuple[int, int]:
    unit = base_price_cents + sum(modifier_prices)
    return unit, unit * quantity


def add_line(cart: Cart, line: LineItem) -> Cart:
    cart.lines.append(line)
    return cart


def remove_line(cart: Cart, line_id: str) -> Cart:
    cart.lines = [ln for ln in cart.lines if ln.line_id != line_id]
    return cart


def find_line(cart: Cart, line_id: str) -> LineItem | None:
    for line in cart.lines:
        if line.line_id == line_id:
            return line
    return None
