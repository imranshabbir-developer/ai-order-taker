from __future__ import annotations

import uuid
from copy import deepcopy

from order_engine.cart_ops import (
    add_line,
    compute_line_pricing,
    find_line,
    remove_line,
    replace_line,
)
from order_engine.catalog import MenuCatalog
from order_engine.models import Cart, LineItem, MenuItemDef, OrderResultStatus
from order_engine.renderers import SummaryRenderer
from order_engine.results import AddItemResult, OperationResult


class OrderService:
    """Deterministic order operations — LLM proposes, this service validates and commits."""

    def __init__(self, catalog: MenuCatalog, cart: Cart | None = None) -> None:
        self.catalog = catalog
        self.cart = cart or Cart(restaurant_id=catalog.config.restaurant_id)

    def search_menu(self, query: str) -> OperationResult:
        matches = self.catalog.search_items(query)
        if not matches:
            return OperationResult(
                status=OrderResultStatus.NOT_FOUND,
                message=(
                    f"I couldn't find anything matching '{query}'. "
                    "Could you describe it differently?"
                ),
                cart=self.cart,
            )
        if len(matches) == 1:
            return OperationResult(
                status=OrderResultStatus.SUCCESS,
                message=f"Found: {matches[0][0].name}",
                cart=self.cart,
                options=[matches[0][0].name],
            )
        options = [m[0].name for m in matches]
        return OperationResult(
            status=OrderResultStatus.CLARIFICATION,
            message="I found a few options. Which one would you like?",
            cart=self.cart,
            options=options,
        )

    def check_ambiguity(self, query: str) -> OperationResult:
        ambiguous = self.catalog.find_ambiguous_category_matches(query)
        if len(ambiguous) > 1:
            options = [a.name for a in ambiguous]
            return OperationResult(
                status=OrderResultStatus.CLARIFICATION,
                message=(
                    "We have several options with that ingredient. "
                    + ", ".join(options)
                    + ". Which would you like?"
                ),
                cart=self.cart,
                options=options,
            )
        return OperationResult(
            status=OrderResultStatus.NOT_FOUND,
            message="No ambiguity detected.",
            cart=self.cart,
        )

    def add_item(
        self,
        item_term: str,
        requested_modifiers: list[str] | None = None,
        quantity: int = 1,
        special_instructions: str = "",
        force_item_id: str | None = None,
    ) -> AddItemResult:
        requested_modifiers = requested_modifiers or []

        item: MenuItemDef | None = None
        if force_item_id:
            item = self.catalog.get_item(force_item_id)
        else:
            bundle_matches = self.catalog.search_bundles(item_term)
            if bundle_matches:
                return self._add_bundle(bundle_matches[0].id, special_instructions, quantity)

            matches = self.catalog.search_items(item_term, limit=3)
            if not matches:
                return AddItemResult(
                    status=OrderResultStatus.NOT_FOUND,
                    message=f"I don't see '{item_term}' on our menu. Could you try another name?",
                    cart=self.cart,
                )
            if len(matches) > 1 and matches[0][1] - matches[1][1] < 10:
                options = [m[0].name for m in matches]
                return AddItemResult(
                    status=OrderResultStatus.CLARIFICATION,
                    message="Which one did you mean? " + ", ".join(options),
                    options=options,
                    cart=self.cart,
                )
            item = matches[0][0]

        assert item is not None

        restriction = item.restriction
        if restriction and restriction.min_notice_hours:
            return AddItemResult(
                status=OrderResultStatus.ADVANCE_NOTICE,
                message=restriction.message
                or (
                    f"{item.name} requires at least {restriction.min_notice_hours} hours notice. "
                    "Please call the store directly to place this order."
                ),
                cart=self.cart,
            )

        resolved_mod_ids, mod_error = self._resolve_modifiers(item, requested_modifiers)
        if mod_error:
            return mod_error

        validation_error = self._validate_modifier_rules(item, resolved_mod_ids)
        if validation_error:
            return validation_error

        final_mod_ids = self._apply_defaults(item, resolved_mod_ids)
        line = self._build_line(item, final_mod_ids, quantity, special_instructions)
        add_line(self.cart, line)

        return AddItemResult(
            status=OrderResultStatus.SUCCESS,
            message=f"Added {line.item_name} to your order.",
            line_id=line.line_id,
            cart=self.cart,
        )

    def add_item_by_id(
        self,
        item_id: str,
        requested_modifiers: list[str] | None = None,
        quantity: int = 1,
        special_instructions: str = "",
    ) -> AddItemResult:
        return self.add_item(
            item_term="",
            requested_modifiers=requested_modifiers,
            quantity=quantity,
            special_instructions=special_instructions,
            force_item_id=item_id,
        )

    def _add_bundle(self, bundle_id: str, note: str, quantity: int) -> AddItemResult:
        bundle = self.catalog.get_bundle(bundle_id)
        if not bundle:
            return AddItemResult(
                status=OrderResultStatus.NOT_FOUND,
                message="Bundle not found.",
                cart=self.cart,
            )
        if bundle.supports_gift_note and note:
            self.cart.order_note = note
        line = LineItem(
            line_id=str(uuid.uuid4())[:8],
            item_id=bundle.id,
            item_name=bundle.name,
            quantity=quantity,
            unit_price_cents=bundle.base_price_cents,
            line_total_cents=bundle.base_price_cents * quantity,
        )
        add_line(self.cart, line)
        msg = f"Added {bundle.name} to your order."
        if note:
            msg += f" Gift note: {note}"
        return AddItemResult(
            status=OrderResultStatus.SUCCESS,
            message=msg,
            line_id=line.line_id,
            cart=self.cart,
        )

    def _resolve_modifiers(
        self, item: MenuItemDef, requested: list[str]
    ) -> tuple[list[str], AddItemResult | None]:
        resolved: list[str] = []
        for term in requested:
            term_lower = term.strip().lower()
            if term_lower in ("no sugar", "without sugar", "unsweetened", "sugar free"):
                resolved.append("no_sugar")
                continue
            if term_lower.startswith("no "):
                mod_name = term_lower[3:]
                mod_id = self.catalog.resolve_modifier_term(mod_name)
                if mod_id:
                    resolved.append(f"exclude:{mod_id}")
                continue
            if term_lower in ("scoop the dough", "scoop dough"):
                continue

            mod_id = self.catalog.resolve_modifier_term(term)
            if not mod_id:
                return [], AddItemResult(
                    status=OrderResultStatus.NOT_FOUND,
                    message=f"I don't recognize the modifier '{term}' for {item.name}.",
                    cart=self.cart,
                )
            if mod_id in item.disallowed_modifier_ids:
                rule_msg = self._cross_item_message(item.id, mod_id)
                return [], AddItemResult(
                    status=OrderResultStatus.VIOLATION,
                    message=rule_msg or f"{term} is not available with {item.name}.",
                    cart=self.cart,
                )
            is_extra = term_lower.startswith("extra") or mod_id.startswith("extra_")
            resolved.append(f"extra:{mod_id}" if is_extra else mod_id)
        return resolved, None

    def _cross_item_message(self, item_id: str, mod_id: str) -> str | None:
        for rule in self.catalog.config.cross_item_rules:
            if rule.item_id == item_id and mod_id in rule.disallowed_modifier_ids:
                return rule.message
        return None

    def _validate_modifier_rules(
        self, item: MenuItemDef, mod_ids: list[str]
    ) -> AddItemResult | None:
        clean_ids = [m for m in mod_ids if not m.startswith(("exclude:", "extra:"))]
        exclude_ids = [m.split(":", 1)[1] for m in mod_ids if m.startswith("exclude:")]

        for group_id in item.modifier_group_ids:
            group = self.catalog.get_group(group_id)
            if not group:
                continue
            selected = [m for m in clean_ids if m in group.modifier_ids]
            if group.max_selections == 1 and len(selected) > 1:
                names = [
                    mod.name for m in selected if (mod := self.catalog.get_modifier(m)) is not None
                ]
                return AddItemResult(
                    status=OrderResultStatus.VIOLATION,
                    message=(
                        f"You can only choose one option from {group.name}. "
                        f"You asked for: {', '.join(names)}."
                    ),
                    cart=self.cart,
                )

            effective = set(selected) - set(exclude_ids)
            has_default = bool(group.default_modifier_ids or item.default_modifier_ids)
            if group.min_selections > 0 and len(effective) == 0 and not has_default:
                options = [
                    mod.name
                    for m in group.modifier_ids
                    if (mod := self.catalog.get_modifier(m)) is not None
                ]
                return AddItemResult(
                    status=OrderResultStatus.CLARIFICATION,
                    message=f"Which {group.name} would you like? Options: {', '.join(options)}",
                    options=options,
                    cart=self.cart,
                )
        return None

    def _apply_defaults(self, item: MenuItemDef, mod_ids: list[str]) -> list[str]:
        result = list(mod_ids)
        exclude_ids = {m.split(":", 1)[1] for m in mod_ids if m.startswith("exclude:")}
        clean = [m for m in mod_ids if not m.startswith(("exclude:", "extra:"))]

        # no_sugar overrides default sweetener (mutually exclusive group)
        if "no_sugar" in clean:
            exclude_ids.add("sugar_default")
            result = [m for m in result if m != "sugar_default"]

        for default_id in item.default_modifier_ids:
            if default_id not in clean and default_id not in exclude_ids:
                result.append(default_id)

        for group_id in item.modifier_group_ids:
            group = self.catalog.get_group(group_id)
            if not group:
                continue
            group_selected = [m for m in clean if m in group.modifier_ids]
            # Sweetener group: no_sugar and sugar_default are mutually exclusive
            if group.id == "coffee_sweetener" and "no_sugar" in clean:
                group_selected = [m for m in group_selected if m != "sugar_default"]
            if not group_selected:
                for default_id in group.default_modifier_ids:
                    if default_id not in exclude_ids and default_id not in result:
                        result.append(default_id)
        return result

    def _build_line(
        self,
        item: MenuItemDef,
        mod_ids: list[str],
        quantity: int,
        special_instructions: str,
    ) -> LineItem:
        mod_names: list[str] = []
        mod_prices: list[int] = []
        exclude_ids = {m.split(":", 1)[1] for m in mod_ids if m.startswith("exclude:")}
        extra_ids = {m.split(":", 1)[1] for m in mod_ids if m.startswith("extra:")}
        if "no_sugar" in mod_ids:
            exclude_ids.add("sugar_default")

        for mid in mod_ids:
            if mid.startswith(("exclude:", "extra:")):
                base_id = mid.split(":", 1)[1]
                mod = self.catalog.get_modifier(base_id)
                if mod:
                    if mid.startswith("exclude:"):
                        mod_names.append(f"no {mod.name}")
                    else:
                        mod_names.append(f"extra {mod.name}")
                        mod_prices.append(mod.price_cents)
                continue
            if mid in exclude_ids:
                continue
            mod = self.catalog.get_modifier(mid)
            if mod and mid not in exclude_ids:
                prefix = "extra " if mid in extra_ids else ""
                mod_names.append(f"{prefix}{mod.name}".strip())
                mod_prices.append(mod.price_cents if mid in extra_ids else mod.price_cents)

        unit, total = compute_line_pricing(item.base_price_cents, mod_prices, quantity)
        return LineItem(
            line_id=str(uuid.uuid4())[:8],
            item_id=item.id,
            item_name=item.name,
            quantity=quantity,
            modifier_ids=[m for m in mod_ids if not m.startswith("exclude:")],
            modifier_names=mod_names,
            special_instructions=special_instructions,
            unit_price_cents=unit,
            line_total_cents=total,
        )

    def set_order_type(self, order_type: str) -> OperationResult:
        allowed = {"pickup", "delivery", "scheduled_pickup", "scheduled_delivery"}
        if order_type not in allowed:
            return OperationResult(
                status=OrderResultStatus.VIOLATION,
                message=f"Order type must be one of: {', '.join(sorted(allowed))}",
                cart=self.cart,
            )
        self.cart.order_type = order_type
        return OperationResult(
            status=OrderResultStatus.SUCCESS,
            message=f"Order type set to {order_type.replace('_', ' ')}.",
            cart=self.cart,
        )

    def remove_item(self, line_id: str) -> OperationResult:
        if not find_line(self.cart, line_id):
            return OperationResult(
                status=OrderResultStatus.NOT_FOUND,
                message="I couldn't find that item in your order.",
                cart=self.cart,
            )
        remove_line(self.cart, line_id)
        return OperationResult(
            status=OrderResultStatus.SUCCESS,
            message="Removed that item from your order.",
            cart=self.cart,
        )

    def set_modifiers(self, line_id: str, requested_modifiers: list[str]) -> OperationResult:
        line = find_line(self.cart, line_id)
        if line is None:
            return OperationResult(
                status=OrderResultStatus.NOT_FOUND,
                message="I couldn't find that item in your order.",
                cart=self.cart,
            )

        item = self.catalog.get_item(line.item_id)
        if item is None:
            bundle = self.catalog.get_bundle(line.item_id)
            if bundle is None:
                return OperationResult(
                    status=OrderResultStatus.NOT_FOUND,
                    message="That menu item is no longer available.",
                    cart=self.cart,
                )
            return OperationResult(
                status=OrderResultStatus.VIOLATION,
                message="Modifiers cannot be changed on bundle items.",
                cart=self.cart,
            )

        resolved_mod_ids, mod_error = self._resolve_modifiers(item, requested_modifiers)
        if mod_error:
            return OperationResult(
                status=mod_error.status,
                message=mod_error.message,
                options=mod_error.options,
                cart=self.cart,
            )

        validation_error = self._validate_modifier_rules(item, resolved_mod_ids)
        if validation_error:
            return OperationResult(
                status=validation_error.status,
                message=validation_error.message,
                options=validation_error.options,
                cart=self.cart,
            )

        final_mod_ids = self._apply_defaults(item, resolved_mod_ids)
        new_line = self._build_line(
            item,
            final_mod_ids,
            line.quantity,
            line.special_instructions,
        )
        new_line.line_id = line.line_id
        replace_line(self.cart, line_id, new_line)
        return OperationResult(
            status=OrderResultStatus.SUCCESS,
            message=f"Updated modifiers for {line.item_name}.",
            cart=self.cart,
        )

    def get_cart(self) -> OperationResult:
        return OperationResult(
            status=OrderResultStatus.SUCCESS,
            message="Current cart",
            cart=self.cart,
        )

    def get_summary(self) -> tuple[str, str]:
        return SummaryRenderer.spoken(self.cart), SummaryRenderer.sms(self.cart)

    def clone_cart(self) -> Cart:
        return deepcopy(self.cart)
