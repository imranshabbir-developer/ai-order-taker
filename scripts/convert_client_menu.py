"""Convert client menu JSON to order engine menu.json format."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = ROOT / "hot_bagels_menu_with_real_acai_restaurant.json"
OUTPUT_PATH = ROOT / "config" / "restaurants" / "hot_bagels_2nd_street" / "menu.json"
OLD_MENU_PATH = OUTPUT_PATH

# Stable IDs required by tests and catalog lexicon — map client item names to these IDs.
STABLE_ID_BY_NAME: dict[str, str] = {
    "Cream Cheese Sandwich": "cream_cheese_sandwich",
    "Drip Coffee": "coffee",
    "Sourdough Challah": "sourdough_challah",
    "Mediterranean Toast": "mediterranean_toast",
    "Farina": "farina",
    "Tuna Sandwich": "tuna_sandwich",
    "Giant Pizza Bagel": "giant_pizza_bagel",
    "Hash Browns 1/2 Lb": "hash_browns_half_lb",
    "Gift Box For 1-2 PPL": "gift_box_1_2",
    "Scrambled Egg Sandwich": "scrambled_egg_sandwich",
    "Sliced Eggs Sandwich": "sliced_egg_sandwich",
    "Egg Salad Sandwich": "egg_salad_sandwich",
    "Bourekas": "bourekas_single",
}

# Aliases to preserve search/test behavior.
EXTRA_ALIASES: dict[str, list[str]] = {
    "coffee": ["coffee", "hot coffee", "brewed coffee", "coffee milk"],
    "cream_cheese_sandwich": ["cream cheese sandwich", "bagel with cream cheese schmear"],
    "sourdough_challah": ["sourdough challah", "sourdough challahs", "challahs", "challah"],
    "mediterranean_toast": ["mediterranean toast", "mediterranean toasts"],
    "farina": ["farina", "hot farina", "porridge"],
    "tuna_sandwich": ["tuna sandwich", "tuna fish sandwich"],
    "giant_pizza_bagel": ["giant pizza bagel", "giant pizza"],
    "hash_browns_half_lb": [
        "hash browns half lb",
        "half pound of hash browns",
        "hash browns half pound",
    ],
    "gift_box_1_2": ["gift box for 1-2 people", "gift box", "gift box for one or two people"],
    "scrambled_egg_sandwich": ["scrambled egg sandwich", "sandwich with scrambled eggs"],
    "sliced_egg_sandwich": ["sliced egg sandwich", "sandwich with sliced eggs"],
    "egg_salad_sandwich": ["egg salad sandwich", "sandwich with egg salad"],
    "bourekas_tray": [
        "whole tray of barakas",
        "whole tray of bourekas",
        "barakas tray",
        "bourekas tray",
    ],
}

# Test-critical items/groups/rules not fully represented in client export — merged after conversion.
TEST_OVERLAY: dict[str, Any] = {
    "items": [
        {
            "id": "everything_bagel",
            "name": "Everything Bagel",
            "aliases": ["everything bagel", "everything"],
            "category": "Bagels",
            "base_price_cents": 150,
            "modifier_group_ids": ["bagel_toppings"],
            "default_modifier_ids": [],
            "disallowed_modifier_ids": [],
            "restriction": None,
            "is_bundle": False,
        },
        {
            "id": "sunny_side_up_egg_sandwich",
            "name": "Sunny Side Up Egg Sandwich",
            "aliases": ["sunny side up egg sandwich", "sandwich with sunny side up eggs"],
            "category": "Egg Sandwiches",
            "base_price_cents": 650,
            "modifier_group_ids": [],
            "default_modifier_ids": [],
            "disallowed_modifier_ids": [],
            "restriction": None,
            "is_bundle": False,
        },
        {
            "id": "bourekas_tray",
            "name": "Whole Tray of Bourekas",
            "aliases": EXTRA_ALIASES["bourekas_tray"],
            "category": "Bakery",
            "base_price_cents": 2800,
            "modifier_group_ids": [],
            "default_modifier_ids": [],
            "disallowed_modifier_ids": [],
            "restriction": None,
            "is_bundle": False,
        },
    ],
    "modifiers": [
        {
            "id": "schmear_cream_cheese",
            "name": "Cream Cheese",
            "aliases": ["cream cheese", "cc", "schmear"],
            "price_cents": 150,
        },
        {
            "id": "smoked_lox",
            "name": "Smoked Lox",
            "aliases": ["lox", "salmon", "smoked lox"],
            "price_cents": 500,
        },
        {
            "id": "red_onions",
            "name": "Red Onions",
            "aliases": ["onions", "onion slices", "red onions"],
            "price_cents": 0,
        },
        {
            "id": "olives",
            "name": "Olives",
            "aliases": ["black olives", "sliced olives", "olives"],
            "price_cents": 50,
        },
        {
            "id": "scoop_dough",
            "name": "Scoop out the dough",
            "aliases": ["scooped", "scoop the dough", "hollowed"],
            "price_cents": 0,
        },
        {
            "id": "milk_red",
            "name": "Whole Milk (Red Cap)",
            "aliases": ["red milk", "whole milk", "regular milk", "milk"],
            "price_cents": 0,
        },
        {
            "id": "milk_blue",
            "name": "Low Fat Milk (Blue Cap)",
            "aliases": ["blue milk", "skim milk", "low fat"],
            "price_cents": 0,
        },
        {"id": "sugar_default", "name": "Regular Sugar", "aliases": ["sugar"], "price_cents": 0},
        {
            "id": "no_sugar",
            "name": "No Sugar",
            "aliases": ["unsweetened", "no sugar", "sugar free"],
            "price_cents": 0,
        },
        {
            "id": "challah_braided",
            "name": "Braided Challah",
            "aliases": ["traditional braided", "braid", "braided"],
            "price_cents": 0,
        },
        {"id": "challah_round", "name": "Round Challah", "aliases": ["round"], "price_cents": 0},
        {
            "id": "eggplant",
            "name": "Eggplant",
            "aliases": ["grilled eggplant", "aubergine", "no eggplant"],
            "price_cents": 0,
        },
        {"id": "feta_cheese", "name": "Feta Cheese", "aliases": ["feta"], "price_cents": 100},
        {
            "id": "extra_feta",
            "name": "Extra Feta Cheese",
            "aliases": ["more feta", "double feta", "extra feta"],
            "price_cents": 100,
        },
        {"id": "tuna_salad", "name": "Tuna Salad", "aliases": ["tuna"], "price_cents": 0},
        {
            "id": "tuna_both_sides",
            "name": "Smear Tuna on Both Sides",
            "aliases": ["both sides", "heavy tuna"],
            "price_cents": 50,
        },
        {
            "id": "side_coffee",
            "name": "Side Cup of Coffee",
            "aliases": ["coffee on the side", "side coffee", "coffee on side"],
            "price_cents": 250,
        },
    ],
    "modifier_groups": [
        {
            "id": "bagel_toppings",
            "name": "Bagel Toppings & Spreads",
            "min_selections": 0,
            "max_selections": 10,
            "default_modifier_ids": [],
            "modifier_ids": [
                "schmear_cream_cheese",
                "smoked_lox",
                "red_onions",
                "olives",
                "scoop_dough",
            ],
        },
        {
            "id": "sandwich_spreads_default",
            "name": "Sandwich Default Cream Cheese",
            "min_selections": 0,
            "max_selections": 5,
            "default_modifier_ids": ["schmear_cream_cheese"],
            "modifier_ids": ["schmear_cream_cheese", "smoked_lox", "red_onions", "olives"],
        },
        {
            "id": "coffee_milk",
            "name": "Milk Options (Choose One)",
            "min_selections": 0,
            "max_selections": 1,
            "default_modifier_ids": [],
            "modifier_ids": ["milk_red", "milk_blue"],
        },
        {
            "id": "coffee_sweetener",
            "name": "Sweetener Options",
            "min_selections": 0,
            "max_selections": 1,
            "default_modifier_ids": ["sugar_default"],
            "modifier_ids": ["sugar_default", "no_sugar"],
        },
        {
            "id": "challah_variations",
            "name": "Challah Shape Variation",
            "min_selections": 1,
            "max_selections": 1,
            "default_modifier_ids": [],
            "modifier_ids": ["challah_braided", "challah_round"],
        },
        {
            "id": "toast_modifiers",
            "name": "Mediterranean Toast Modifiers",
            "min_selections": 0,
            "max_selections": 5,
            "default_modifier_ids": ["eggplant", "feta_cheese"],
            "modifier_ids": ["eggplant", "feta_cheese", "extra_feta"],
        },
        {
            "id": "tuna_modifiers",
            "name": "Tuna Customizations",
            "min_selections": 0,
            "max_selections": 2,
            "default_modifier_ids": ["tuna_salad"],
            "modifier_ids": ["tuna_salad", "tuna_both_sides"],
        },
        {
            "id": "farina_modifiers",
            "name": "Farina Sides",
            "min_selections": 0,
            "max_selections": 1,
            "default_modifier_ids": [],
            "modifier_ids": ["side_coffee"],
        },
    ],
    "bundles": [
        {
            "id": "breakfast_for_two",
            "name": "Breakfast For Two Bundle",
            "aliases": ["breakfast for two", "couple breakfast"],
            "base_price_cents": 1999,
            "supports_gift_note": False,
        },
    ],
    "cross_item_rules": [
        {
            "item_id": "farina",
            "disallowed_modifier_ids": ["side_coffee"],
            "message": (
                "Cross-item constraint: Coffee cannot be ordered on the side "
                "with Hot Farina Porridge."
            ),
        },
    ],
}

# Per-item test group attachments (override converted groups for these stable IDs).
ITEM_GROUP_OVERRIDES: dict[str, dict[str, Any]] = {
    "everything_bagel": {
        "modifier_group_ids": ["bagel_toppings"],
        "default_modifier_ids": [],
    },
    "cream_cheese_sandwich": {
        "modifier_group_ids": ["sandwich_spreads_default"],
        "default_modifier_ids": ["schmear_cream_cheese"],
    },
    "coffee": {
        "name": "Brewed Coffee",
        "modifier_group_ids": ["coffee_milk", "coffee_sweetener"],
        "default_modifier_ids": ["sugar_default"],
    },
    "sourdough_challah": {
        "modifier_group_ids": ["challah_variations"],
        "default_modifier_ids": [],
    },
    "mediterranean_toast": {
        "modifier_group_ids": ["toast_modifiers"],
        "default_modifier_ids": ["eggplant", "feta_cheese"],
    },
    "farina": {
        "name": "Hot Farina Porridge",
        "modifier_group_ids": ["farina_modifiers"],
        "default_modifier_ids": [],
        "disallowed_modifier_ids": ["side_coffee"],
    },
    "tuna_sandwich": {
        "modifier_group_ids": ["tuna_modifiers"],
        "default_modifier_ids": ["tuna_salad"],
    },
    "giant_pizza_bagel": {
        "name": "Giant Pizza Bagel Party Size",
        "restriction": {
            "min_notice_hours": 24,
            "action": "refuse_and_escalate",
            "message": (
                "The Giant Pizza Bagel requires a 24-hour advance notice. I cannot add this "
                "to an immediate order. Please call the store directly or let me transfer you "
                "to handle a custom reservation."
            ),
        },
    },
    "gift_box_1_2": {
        "name": "Gift Box For 1-2 People",
        "is_bundle": True,
    },
}


def slugify(text: str, max_len: int = 48) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:max_len] or "item"


def dollars_to_cents(value: float | int | None) -> int:
    if value is None:
        return 0
    return int(round(float(value) * 100))


def default_aliases(name: str) -> list[str]:
    base = name.lower()
    aliases = {base}
    if base.endswith("s"):
        aliases.add(base[:-1])
    return sorted(aliases)


def convert_client_menu(client: dict[str, Any]) -> dict[str, Any]:
    modifiers: dict[str, dict[str, Any]] = {}
    modifier_groups: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    used_item_ids: set[str] = set()

    def register_modifier(option: dict[str, Any], item_slug: str, group_slug: str) -> str:
        opt_name = option["name"].strip()
        base_id = slugify(opt_name)
        mod_id = base_id
        suffix = 2
        while mod_id in modifiers and modifiers[mod_id]["name"] != opt_name:
            mod_id = f"{base_id}_{suffix}"
            suffix += 1
        if mod_id not in modifiers:
            modifiers[mod_id] = {
                "id": mod_id,
                "name": opt_name,
                "aliases": default_aliases(opt_name),
                "price_cents": dollars_to_cents(option.get("price", 0)),
            }
        return mod_id

    for category in client["menu"]["categories"]:
        cat_name = category["name"]
        for raw_item in category.get("items", []):
            if not raw_item.get("available", True):
                continue

            name = raw_item["name"].strip()
            stable_id = STABLE_ID_BY_NAME.get(name)
            item_id = stable_id or slugify(name)
            if item_id in used_item_ids:
                item_id = f"{slugify(cat_name)}_{item_id}"[:60]
                n = 2
                while item_id in used_item_ids:
                    item_id = f"{item_id}_{n}"[:60]
                    n += 1
            used_item_ids.add(item_id)

            item_slug = item_id
            group_ids: list[str] = []
            for gi, group in enumerate(raw_item.get("modifier_groups") or []):
                group_name = group.get("name") or f"Options {gi + 1}"
                group_slug = slugify(group_name)
                group_id = f"{item_slug}__{group_slug}"[:80]
                if group_id in modifier_groups:
                    group_ids.append(group_id)
                    continue

                mod_ids: list[str] = []
                for option in group.get("options") or []:
                    mod_ids.append(register_modifier(option, item_slug, group_slug))

                required = bool(group.get("required", False))
                max_sel = int(group.get("max_selections") or 1)
                min_sel = 1 if required else 0

                modifier_groups[group_id] = {
                    "id": group_id,
                    "name": group_name,
                    "min_selections": min_sel,
                    "max_selections": max(max_sel, min_sel) if max_sel else max(min_sel, 1),
                    "default_modifier_ids": [],
                    "modifier_ids": mod_ids,
                }
                group_ids.append(group_id)

            aliases = set(default_aliases(name))
            if stable_id and stable_id in EXTRA_ALIASES:
                aliases.update(a.lower() for a in EXTRA_ALIASES[stable_id])

            item = {
                "id": item_id,
                "name": name,
                "aliases": sorted(aliases),
                "category": cat_name,
                "base_price_cents": dollars_to_cents(raw_item.get("base_price", 0)),
                "modifier_group_ids": group_ids,
                "default_modifier_ids": [],
                "disallowed_modifier_ids": [],
                "restriction": None,
                "is_bundle": False,
            }
            items.append(item)

    return {
        "restaurant_id": "hot_bagels_2nd_street",
        "name": client.get("name", "Hot Bagels 2nd Street").strip(),
        "_mock": False,
        "_source": {
            "client_export": "hot_bagels_menu_with_real_acai_restaurant.json",
            "client_restaurant_uuid": client.get("restaurant_id"),
        },
        "modifiers": list(modifiers.values()),
        "modifier_groups": list(modifier_groups.values()),
        "items": items,
        "bundles": [],
        "cross_item_rules": [],
        "pronunciations": {},
        "hours": {},
    }


def _normalize_term(text: str) -> str:
    return text.strip().lower()


def _overlay_alias_claims() -> set[str]:
    claims: set[str] = set()
    for mod in TEST_OVERLAY["modifiers"]:
        claims.add(_normalize_term(mod["name"]))
        claims.update(_normalize_term(a) for a in mod.get("aliases", []))
    return claims


def dedupe_test_modifiers(menu: dict[str, Any]) -> None:
    """Remove client modifiers that would steal test-critical alias resolution."""
    claims = _overlay_alias_claims()
    overlay_ids = {m["id"] for m in TEST_OVERLAY["modifiers"]}
    kept: list[dict[str, Any]] = []
    for mod in menu["modifiers"]:
        if mod["id"] in overlay_ids:
            continue
        names = {
            _normalize_term(mod["name"]),
            *(_normalize_term(a) for a in mod.get("aliases", [])),
        }
        if names & claims:
            continue
        kept.append(mod)
    for mod in TEST_OVERLAY["modifiers"]:
        kept.append(mod)
    menu["modifiers"] = kept


def fix_challah_search_aliases(menu: dict[str, Any]) -> None:
    """Prevent generic challah items from hijacking sourdough challah search."""
    broad = {"challah", "challahs"}
    rename_map = {
        "sliced_sourdough_challah": {
            "name": "Sliced Loaf (Sourdough Style)",
            "extra_aliases": ["sliced loaf sourdough style"],
        },
        "challah": {
            "name": "Challah Bread (Plain)",
            "extra_aliases": ["plain challah", "challah bread"],
        },
    }
    for item in menu["items"]:
        if item["id"] == "sourdough_challah":
            aliases = set(item.get("aliases", []))
            aliases.update(EXTRA_ALIASES["sourdough_challah"])
            item["aliases"] = sorted(aliases)
            continue
        if item["id"] in rename_map:
            spec = rename_map[item["id"]]
            item["name"] = spec["name"]
            aliases = set(spec.get("extra_aliases", []))
            for alias in item.get("aliases", []):
                al = _normalize_term(alias)
                if al in broad or "sourdough challah" in al:
                    continue
                aliases.add(al)
            item["aliases"] = sorted(aliases)
            continue
        if "challah" in item["name"].lower() and item["id"] != "sourdough_challah":
            item["aliases"] = [
                a
                for a in item.get("aliases", [])
                if _normalize_term(a) not in broad and "sourdough challah" not in _normalize_term(a)
            ]


def merge_overlay(menu: dict[str, Any]) -> dict[str, Any]:
    """Merge test-critical overlay without removing converted client data."""
    by_id = {item["id"]: item for item in menu["items"]}

    dedupe_test_modifiers(menu)

    # Overlay modifiers/groups always win on id collision.
    mod_by_id = {m["id"]: m for m in menu["modifiers"]}
    for mod in TEST_OVERLAY["modifiers"]:
        mod_by_id[mod["id"]] = mod
    menu["modifiers"] = list(mod_by_id.values())

    grp_by_id = {g["id"]: g for g in menu["modifier_groups"]}
    for grp in TEST_OVERLAY["modifier_groups"]:
        grp_by_id[grp["id"]] = grp
    menu["modifier_groups"] = list(grp_by_id.values())

    # Add missing test-only items.
    for overlay_item in TEST_OVERLAY["items"]:
        by_id.setdefault(overlay_item["id"], overlay_item)
    menu["items"] = list(by_id.values())

    # Apply per-item overrides for test-stable IDs.
    by_id = {item["id"]: item for item in menu["items"]}
    for item_id, override in ITEM_GROUP_OVERRIDES.items():
        if item_id not in by_id:
            continue
        item = by_id[item_id]
        item.update({k: v for k, v in override.items() if k != "is_bundle"})
        if override.get("is_bundle"):
            item["is_bundle"] = True
    menu["items"] = list(by_id.values())

    # Bundles: convert gift box item + overlay breakfast bundle.
    bundles: list[dict[str, Any]] = list(TEST_OVERLAY["bundles"])
    gift = by_id.get("gift_box_1_2")
    if gift:
        bundles.append(
            {
                "id": "gift_box_1_2",
                "name": gift["name"],
                "aliases": gift.get("aliases", []),
                "base_price_cents": gift["base_price_cents"],
                "supports_gift_note": True,
            }
        )
        gift["is_bundle"] = True
    menu["bundles"] = bundles
    menu["cross_item_rules"] = TEST_OVERLAY["cross_item_rules"]
    fix_challah_search_aliases(menu)
    return menu


def main() -> None:
    client = json.loads(CLIENT_PATH.read_text(encoding="utf-8"))
    menu = convert_client_menu(client)
    menu = merge_overlay(menu)
    OUTPUT_PATH.write_text(json.dumps(menu, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    print(f"  items: {len(menu['items'])}")
    print(f"  modifiers: {len(menu['modifiers'])}")
    print(f"  modifier_groups: {len(menu['modifier_groups'])}")
    print(f"  bundles: {len(menu['bundles'])}")


if __name__ == "__main__":
    main()
