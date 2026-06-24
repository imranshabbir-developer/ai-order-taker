from __future__ import annotations

import os

import pytest
from httpx import AsyncClient

from apps.order_api.settings import get_settings
from tests.integration.conftest import RESTAURANT_ID, api_path


@pytest.mark.asyncio
async def test_store_closed_blocks_add_item(client: AsyncClient, call_id: str) -> None:
    os.environ["ENFORCE_STORE_HOURS"] = "true"
    get_settings.cache_clear()

    from unittest.mock import patch

    from apps.order_api.use_cases import use_cases

    await client.post(api_path(RESTAURANT_ID, call_id, "/reset"))
    with patch.object(
        use_cases,
        "_ensure_store_open",
        return_value=use_cases._closed_result(
            await use_cases.get_service(RESTAURANT_ID, call_id),
            "We are currently closed.",
        ),
    ):
        r = await client.post(
            api_path(RESTAURANT_ID, call_id, "/tools/add_item"),
            json={"item_term": "coffee"},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "store_closed"

    os.environ["ENFORCE_STORE_HOURS"] = "false"
    get_settings.cache_clear()
