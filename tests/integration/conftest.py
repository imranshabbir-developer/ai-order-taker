from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

# Default integration tests run without Postgres (fast, isolated).
os.environ["DATABASE_URL"] = ""

from apps.order_api.db.engine import init_database  # noqa: E402
from apps.order_api.main import app  # noqa: E402
from apps.order_api.settings import get_settings  # noqa: E402

get_settings.cache_clear()
init_database()

RESTAURANT_ID = "hot_bagels_2nd_street"


@pytest.fixture
def call_id() -> str:
    return f"test-{uuid.uuid4().hex[:12]}"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def api_path(restaurant_id: str, call_id: str, suffix: str) -> str:
    return f"/v1/restaurants/{restaurant_id}/calls/{call_id}{suffix}"
