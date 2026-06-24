"""Sync restaurant rows from config/restaurants/* on startup."""

from __future__ import annotations

from pathlib import Path

from order_engine.config_loader import RestaurantConfigBundle

from apps.order_api.db.session_store import SessionStore


async def sync_restaurants_from_config(config_root: Path) -> int:
    """Ensure every config folder has a restaurants table row. Returns count synced."""
    store = SessionStore()
    count = 0
    if not config_root.exists():
        return 0
    for path in sorted(config_root.iterdir()):
        if not path.is_dir():
            continue
        try:
            bundle = RestaurantConfigBundle.load(path)
        except Exception:
            continue
        name = str(bundle.menu.get("name", bundle.restaurant_id))
        await store.ensure_restaurant(bundle.restaurant_id, name)
        count += 1
    return count
