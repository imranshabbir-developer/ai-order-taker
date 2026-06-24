from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


class OrderResultStatus(StrEnum):
    SUCCESS = "success"
    CLARIFICATION = "clarification"
    VIOLATION = "violation"
    NOT_FOUND = "not_found"
    ADVANCE_NOTICE = "advance_notice"
    STORE_CLOSED = "store_closed"


class ModifierDef(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    price_cents: int = 0


class ModifierGroupDef(BaseModel):
    id: str
    name: str
    min_selections: int = 0
    max_selections: int = 1
    default_modifier_ids: list[str] = Field(default_factory=list)
    modifier_ids: list[str] = Field(default_factory=list)


class ItemRestriction(BaseModel):
    min_notice_hours: int | None = None
    action: str = "refuse_and_advise_call_store"
    message: str = ""


class MenuItemDef(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    category: str
    base_price_cents: int
    modifier_group_ids: list[str] = Field(default_factory=list)
    default_modifier_ids: list[str] = Field(default_factory=list)
    disallowed_modifier_ids: list[str] = Field(default_factory=list)
    restriction: ItemRestriction | None = None
    is_bundle: bool = False


class BundleDef(BaseModel):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    base_price_cents: int
    supports_gift_note: bool = False


class CrossItemRule(BaseModel):
    item_id: str
    disallowed_modifier_ids: list[str] = Field(default_factory=list)
    message: str = ""


class RestaurantConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    restaurant_id: str
    name: str
    items: list[MenuItemDef]
    modifier_groups: list[ModifierGroupDef]
    modifiers: list[ModifierDef]
    bundles: list[BundleDef] = Field(default_factory=list)
    cross_item_rules: list[CrossItemRule] = Field(default_factory=list)
    pronunciations: dict[str, list[str]] = Field(default_factory=dict)
    hours: dict[str, Any] = Field(default_factory=dict)


class LineItem(BaseModel):
    line_id: str
    item_id: str
    item_name: str
    quantity: int = 1
    modifier_ids: list[str] = Field(default_factory=list)
    modifier_names: list[str] = Field(default_factory=list)
    special_instructions: str = ""
    unit_price_cents: int = 0
    line_total_cents: int = 0


class Cart(BaseModel):
    restaurant_id: str
    order_type: str = "pickup"
    lines: list[LineItem] = Field(default_factory=list)
    delivery_address: str = ""
    delivery_instructions: str = ""
    scheduled_at: str | None = None
    order_note: str = ""
    customer_phone: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_cents(self) -> int:
        return sum(line.line_total_cents for line in self.lines)
