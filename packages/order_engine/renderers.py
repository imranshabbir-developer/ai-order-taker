from __future__ import annotations

from order_engine.models import Cart


class SummaryRenderer:
    """Single source of truth for spoken and SMS summaries — must stay identical."""

    @staticmethod
    def render(cart: Cart) -> str:
        if not cart.lines:
            return "Your order is empty."

        parts: list[str] = []
        for line in cart.lines:
            mod_text = ""
            if line.modifier_names:
                mod_text = f" ({', '.join(line.modifier_names)})"
            instr = ""
            if line.special_instructions:
                instr = f" — Note: {line.special_instructions}"
            qty = f"{line.quantity}x " if line.quantity > 1 else ""
            price = f"${line.line_total_cents / 100:.2f}"
            parts.append(f"{qty}{line.item_name}{mod_text}{instr} - {price}")

        total = f"Total: ${cart.total_cents / 100:.2f}"
        header = f"Order type: {cart.order_type.replace('_', ' ').title()}"
        body = "\n".join(parts)
        return f"{header}\n{body}\n{total}"

    @staticmethod
    def spoken(cart: Cart) -> str:
        return SummaryRenderer.render(cart)

    @staticmethod
    def sms(cart: Cart) -> str:
        return SummaryRenderer.render(cart)
