from __future__ import annotations

import json
import re
from pathlib import Path

from order_engine.catalog import MenuCatalog
from rapidfuzz import fuzz


def load_pronunciations(restaurant_id: str) -> dict[str, list[str]]:
    """Map ASR variant -> canonical menu grapheme from pronunciations.json."""
    path = (
        Path(__file__).resolve().parents[2]
        / "config"
        / "restaurants"
        / restaurant_id
        / "pronunciations.json"
    )
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    aliases: dict[str, list[str]] = {}

    if isinstance(payload.get("aliases"), dict):
        return {str(k): list(v) for k, v in payload["aliases"].items()}

    for rule in payload.get("lexicon_rules", []):
        canonical = str(rule.get("grapheme", "")).strip()
        if not canonical:
            continue
        variants = [str(v) for v in rule.get("asr_aliases", []) if v]
        aliases[canonical] = variants

    return aliases


def normalize_transcript(
    text: str,
    catalog: MenuCatalog,
    *,
    pronunciation_aliases: dict[str, list[str]] | None = None,
) -> str:
    """Apply restaurant pronunciation aliases and light menu fuzzy hints to ASR text."""
    normalized = text.strip()
    if not normalized:
        return normalized

    aliases = pronunciation_aliases or {}
    for canonical, variants in aliases.items():
        for variant in variants:
            pattern = re.compile(re.escape(variant), re.IGNORECASE)
            if pattern.search(normalized):
                normalized = pattern.sub(canonical, normalized)

    tokens = re.findall(r"[a-zA-Z']+", normalized.lower())
    if len(tokens) == 1:
        token = tokens[0]
        best_item = None
        best_score = 0
        for item in catalog.config.items:
            names = [item.name.lower(), item.id.replace("_", " ")] + [
                a.lower() for a in item.aliases
            ]
            for name in names:
                score = fuzz.ratio(token, name)
                if score > best_score:
                    best_score = score
                    best_item = item
        if best_item and best_score >= 80:
            normalized = re.sub(
                re.escape(token),
                best_item.name,
                normalized,
                count=1,
                flags=re.IGNORECASE,
            )

    return normalized
