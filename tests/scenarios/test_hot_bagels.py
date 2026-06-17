from __future__ import annotations

from pathlib import Path

import pytest

from order_engine.catalog import MenuCatalog
from order_engine.models import OrderResultStatus
from order_engine.order_service import OrderService
from order_engine.renderers import SummaryRenderer

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "restaurants" / "hot_bagels_2nd_street"


@pytest.fixture
def catalog() -> MenuCatalog:
    return MenuCatalog.from_path(CONFIG_DIR)


@pytest.fixture
def service(catalog: MenuCatalog) -> OrderService:
    return OrderService(catalog)


class TestHotBagelsScenarios:
    """14 critical client test scenarios — deterministic order engine (Gemini mock menu)."""

    def test_01_free_form_bagel_with_modifiers(self, service: OrderService) -> None:
        result = service.add_item(
            "everything bagel",
            requested_modifiers=[
                "cream cheese",
                "smoked lox",
                "red onions",
                "olives",
            ],
            special_instructions="scoop the dough",
        )
        assert result.status == OrderResultStatus.SUCCESS
        line = service.cart.lines[0]
        assert line.item_id == "everything_bagel"
        assert any("Lox" in m for m in line.modifier_names)
        assert line.special_instructions == "scoop the dough"

    def test_02a_default_modifiers_silent(self, service: OrderService) -> None:
        r1 = service.add_item("cream cheese sandwich")
        assert r1.status == OrderResultStatus.SUCCESS
        line1 = service.cart.lines[0]
        assert any("Cream Cheese" in m for m in line1.modifier_names)

        r2 = service.add_item("coffee", requested_modifiers=["milk", "no sugar"])
        assert r2.status == OrderResultStatus.SUCCESS
        line2 = service.cart.lines[1]
        assert any("Milk" in m for m in line2.modifier_names)
        assert "No Sugar" in line2.modifier_names
        assert "Regular Sugar" not in line2.modifier_names

    def test_02b_challah_requires_variation(self, service: OrderService) -> None:
        result = service.add_item("sourdough challah", quantity=2)
        assert result.status == OrderResultStatus.CLARIFICATION
        assert result.options
        opts = " ".join(result.options).lower()
        assert "braided" in opts or "round" in opts

    def test_03_multi_category_egg_ambiguity(self, service: OrderService) -> None:
        result = service.check_ambiguity("sandwich with eggs")
        assert result.status == OrderResultStatus.CLARIFICATION
        assert len(result.options) >= 3
        assert "egg" in " ".join(result.options).lower()

    def test_04_split_modifiers_two_lines(self, service: OrderService) -> None:
        r1 = service.add_item("mediterranean toast", requested_modifiers=["no eggplant"])
        assert r1.status == OrderResultStatus.SUCCESS
        r2 = service.add_item("mediterranean toast", requested_modifiers=["extra feta"])
        assert r2.status == OrderResultStatus.SUCCESS
        assert len(service.cart.lines) == 2
        assert service.cart.lines[0].line_id != service.cart.lines[1].line_id
        assert any("Eggplant" in m for m in service.cart.lines[0].modifier_names)
        assert any("Feta" in m for m in service.cart.lines[1].modifier_names)

    def test_05_conflicting_milk_and_farina_rule(self, service: OrderService) -> None:
        r1 = service.add_item("coffee", requested_modifiers=["red milk", "blue milk"])
        assert r1.status == OrderResultStatus.VIOLATION
        r2 = service.add_item("farina", requested_modifiers=["coffee on side"])
        assert r2.status == OrderResultStatus.VIOLATION

    def test_06_breakfast_for_two_bundle(self, service: OrderService) -> None:
        result = service.add_item("breakfast for two")
        assert result.status == OrderResultStatus.SUCCESS
        assert service.cart.lines[0].item_id == "breakfast_for_two"

    def test_07_gift_box_with_note(self, service: OrderService) -> None:
        result = service.add_item(
            "gift box for 1-2 people",
            special_instructions="Happy Birthday!",
        )
        assert result.status == OrderResultStatus.SUCCESS
        assert service.cart.lines[0].item_id == "gift_box_1_2"
        assert "Happy Birthday" in service.cart.order_note or "Happy Birthday" in result.message

    def test_08_giant_pizza_bagel_advance_notice(self, service: OrderService) -> None:
        result = service.add_item("giant pizza bagel")
        assert result.status == OrderResultStatus.ADVANCE_NOTICE
        assert "24" in result.message
        assert len(service.cart.lines) == 0

    def test_10_special_instructions_tuna(self, service: OrderService) -> None:
        result = service.add_item(
            "tuna sandwich",
            special_instructions="Smear tuna on both sides",
        )
        assert result.status == OrderResultStatus.SUCCESS
        assert service.cart.lines[0].special_instructions == "Smear tuna on both sides"

    def test_11_pronunciation_challah_and_bourekas(self, service: OrderService) -> None:
        r1 = service.add_item_by_id(
            "sourdough_challah",
            requested_modifiers=["braided"],
            quantity=2,
        )
        assert r1.status == OrderResultStatus.SUCCESS
        matches = service.catalog.search_items("barakas")
        assert matches
        assert matches[0][0].id == "bourekas_tray"

    def test_13_sms_spoken_parity(self, service: OrderService) -> None:
        service.add_item("cream cheese sandwich")
        service.add_item("coffee", requested_modifiers=["no sugar"])
        spoken, sms = service.get_summary()
        assert spoken == sms
        assert SummaryRenderer.spoken(service.cart) == SummaryRenderer.sms(service.cart)

    def test_14_post_order_add_hash_browns(self, service: OrderService) -> None:
        service.add_item("cream cheese sandwich")
        first_total = service.cart.total_cents
        result = service.add_item("hash browns half lb")
        assert result.status == OrderResultStatus.SUCCESS
        assert service.cart.total_cents > first_total
        assert any(line.item_id == "hash_browns_half_lb" for line in service.cart.lines)
