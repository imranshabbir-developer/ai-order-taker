from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RestaurantConfigBundle(BaseModel):
    """All config files for one restaurant."""

    restaurant_id: str
    menu: dict[str, Any]
    operations: dict[str, Any] = Field(default_factory=dict)
    integrations: dict[str, Any] = Field(default_factory=dict)
    pronunciations: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load(cls, config_dir: Path) -> RestaurantConfigBundle:
        restaurant_id = config_dir.name

        def _read(name: str) -> dict[str, Any]:
            path = config_dir / name
            if not path.exists():
                return {}
            return json.loads(path.read_text(encoding="utf-8"))

        menu = _read("menu.json")
        if menu:
            restaurant_id = menu.get("restaurant_id", restaurant_id)

        return cls(
            restaurant_id=restaurant_id,
            menu=menu,
            operations=_read("operations.json"),
            integrations=_read("integrations.json"),
            pronunciations=_read("pronunciations.json"),
        )

    @property
    def is_mock(self) -> bool:
        return bool(
            self.menu.get("_mock")
            or self.operations.get("_mock")
            or self.integrations.get("_mock")
        )
