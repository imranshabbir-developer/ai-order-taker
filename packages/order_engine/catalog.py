from __future__ import annotations

import json
from pathlib import Path

from rapidfuzz import fuzz, process

from order_engine.models import (
    MenuItemDef,
    ModifierDef,
    ModifierGroupDef,
    RestaurantConfig,
)

# Grapheme / ASR terms → menu item IDs (Gemini pronunciations.json)
_LEXICON_ITEM_MAP: dict[str, str] = {
    "challah": "sourdough_challah",
    "challahs": "sourdough_challah",
    "bourekas": "bourekas_tray",
    "barakas": "bourekas_tray",
    "borekas": "bourekas_tray",
    "baraka": "bourekas_tray",
}


class MenuCatalog:
    """Loads and queries restaurant menu configuration."""

    def __init__(self, config: RestaurantConfig, config_dir: Path | None = None) -> None:
        self.config = config
        self.config_dir = config_dir
        self._items: dict[str, MenuItemDef] = {i.id: i for i in config.items}
        self._modifiers: dict[str, ModifierDef] = {m.id: m for m in config.modifiers}
        self._groups: dict[str, ModifierGroupDef] = {g.id: g for g in config.modifier_groups}
        self._search_index: list[tuple[str, str]] = self._build_search_index()
        if config_dir:
            self._merge_pronunciations_file(config_dir)

    @classmethod
    def from_path(cls, config_dir: Path) -> MenuCatalog:
        menu_path = config_dir / "menu.json"
        data = json.loads(menu_path.read_text(encoding="utf-8"))
        config = RestaurantConfig.model_validate(data)
        catalog = cls(config, config_dir=config_dir)
        return catalog

    def _merge_pronunciations_file(self, config_dir: Path) -> None:
        path = config_dir / "pronunciations.json"
        if not path.exists():
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        for rule in payload.get("lexicon_rules", []):
            grapheme = rule.get("grapheme", "").lower()
            item_id = _LEXICON_ITEM_MAP.get(grapheme)
            if not item_id and grapheme.endswith("s"):
                item_id = _LEXICON_ITEM_MAP.get(grapheme.rstrip("s"))
            if not item_id:
                continue
            for alias in rule.get("asr_aliases", []):
                self._search_index.append((item_id, alias.lower()))
            self._search_index.append((item_id, grapheme))

    def _build_search_index(self) -> list[tuple[str, str]]:
        index: list[tuple[str, str]] = []
        for item in self.config.items:
            index.append((item.id, item.name.lower()))
            for alias in item.aliases:
                index.append((item.id, alias.lower()))
        for bundle in self.config.bundles:
            index.append((bundle.id, bundle.name.lower()))
            for alias in bundle.aliases:
                index.append((bundle.id, alias.lower()))
        for canonical, variants in self.config.pronunciations.items():
            if canonical in self._items or any(b.id == canonical for b in self.config.bundles):
                for v in variants:
                    index.append((canonical, v.lower()))
        return index

    def get_item(self, item_id: str) -> MenuItemDef | None:
        return self._items.get(item_id)

    def get_modifier(self, modifier_id: str) -> ModifierDef | None:
        return self._modifiers.get(modifier_id)

    def get_group(self, group_id: str) -> ModifierGroupDef | None:
        return self._groups.get(group_id)

    def resolve_modifier_term(self, term: str) -> str | None:
        term_lower = term.strip().lower()
        for mod in self.config.modifiers:
            if mod.name.lower() == term_lower or term_lower in [a.lower() for a in mod.aliases]:
                return mod.id
        choices = [(m.id, m.name.lower()) for m in self.config.modifiers]
        for mod in self.config.modifiers:
            for alias in mod.aliases:
                choices.append((mod.id, alias.lower()))
        match = process.extractOne(term_lower, [c[1] for c in choices], scorer=fuzz.WRatio)
        if match and match[1] >= 75:
            idx = [c[1] for c in choices].index(match[0])
            return choices[idx][0]
        return None

    def search_items(self, query: str, limit: int = 5) -> list[tuple[MenuItemDef, float]]:
        query_lower = query.strip().lower()
        if not query_lower:
            return []

        scored: dict[str, float] = {}
        for item_id, label in self._search_index:
            score = fuzz.WRatio(query_lower, label)
            if score >= 60:
                scored[item_id] = max(scored.get(item_id, 0), score)

        results: list[tuple[MenuItemDef, float]] = []
        seen: set[str] = set()
        for item_id, score in sorted(scored.items(), key=lambda x: -x[1]):
            if item_id in seen:
                continue
            item = self._items.get(item_id)
            if item:
                seen.add(item_id)
                results.append((item, score))
            if len(results) >= limit:
                break
        return results

    def find_ambiguous_category_matches(self, query: str) -> list[MenuItemDef]:
        """Find items sharing an ingredient/category keyword (e.g. 'eggs' sandwiches)."""
        query_lower = query.strip().lower()
        if "egg" in query_lower or "eggs" in query_lower:
            return [
                i
                for i in self.config.items
                if "egg" in i.name.lower() or "egg" in i.category.lower()
            ]
        matched: list[MenuItemDef] = []
        for item in self.config.items:
            haystack = " ".join([item.name.lower(), item.category.lower()] + item.aliases).lower()
            if query_lower in haystack:
                matched.append(item)
        return matched

    def get_bundle(self, bundle_id: str):
        for b in self.config.bundles:
            if b.id == bundle_id:
                return b
        return None

    def search_bundles(self, query: str) -> list:
        query_lower = query.strip().lower()
        results = []
        for b in self.config.bundles:
            labels = [b.name.lower(), *[a.lower() for a in b.aliases]]
            best = max(fuzz.WRatio(query_lower, label) for label in labels)
            if best >= 70 or query_lower in b.name.lower() or any(query_lower in a.lower() for a in b.aliases):
                results.append((b, best))
        results.sort(key=lambda x: -x[1])
        return [b for b, _ in results]

    def items_by_category(self) -> dict[str, list[MenuItemDef]]:
        grouped: dict[str, list[MenuItemDef]] = {}
        for item in self.config.items:
            grouped.setdefault(item.category, []).append(item)
        return grouped
