from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RestaurantPrompts(BaseModel):
    restaurant_id: str
    restaurant_name: str = "Restaurant"
    greeting: str = "Welcome! What would you like to order today?"
    system: str = ""
    rules: list[str] = Field(default_factory=list)
    phase_hints: dict[str, str] = Field(default_factory=dict)

    def render_system(self, phase: str = "ordering") -> str:
        phase_hint = self.phase_hints.get(phase, "")
        rules_block = "\n".join(f"- {rule}" for rule in self.rules)
        return self.system.format(
            restaurant_name=self.restaurant_name,
            phase=phase,
            phase_hint=phase_hint,
            rules=rules_block,
        )


def prompts_path(restaurant_id: str, config_root: Path | None = None) -> Path:
    root = config_root or Path(__file__).resolve().parents[2] / "config" / "restaurants"
    return root / restaurant_id / "prompts.yaml"


def load_prompts(restaurant_id: str, config_root: Path | None = None) -> RestaurantPrompts:
    path = prompts_path(restaurant_id, config_root)
    if not path.exists():
        raise FileNotFoundError(f"Missing prompts.yaml for restaurant '{restaurant_id}': {path}")
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RestaurantPrompts(
        restaurant_id=restaurant_id,
        restaurant_name=str(raw.get("restaurant_name", restaurant_id)),
        greeting=str(raw.get("greeting", "Welcome! What would you like to order today?")),
        system=str(raw.get("system", "")),
        rules=[str(r) for r in raw.get("rules", [])],
        phase_hints={str(k): str(v) for k, v in (raw.get("phase_hints") or {}).items()},
    )
