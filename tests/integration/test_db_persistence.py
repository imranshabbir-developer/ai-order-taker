from __future__ import annotations

import os
import uuid

import pytest
from httpx import AsyncClient

from apps.order_api.db.engine import check_database, close_database, init_database
from apps.order_api.settings import get_settings
from tests.integration.conftest import RESTAURANT_ID, api_path


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB"),
    reason="Set INTEGRATION_DB=1 to run Postgres persistence tests",
)
async def test_checkout_payment_sms_persisted_in_postgres(client: AsyncClient) -> None:
    os.environ.pop("DATABASE_URL", None)
    os.environ["ENFORCE_STORE_HOURS"] = "false"
    get_settings.cache_clear()
    init_database()

    if not get_settings().database_enabled or not await check_database():
        pytest.skip("DATABASE_URL not configured or database unreachable")

    call_id = f"pg-{uuid.uuid4().hex[:8]}"
    phone = "+15557778888"
    await client.post(api_path(RESTAURANT_ID, call_id, "/reset"))
    await client.post(
        api_path(RESTAURANT_ID, call_id, "/start"),
        json={"caller_phone": phone},
    )
    await client.post(
        api_path(RESTAURANT_ID, call_id, "/tools/add_item"),
        json={"item_term": "cream cheese sandwich"},
    )
    checkout = await client.post(
        api_path(RESTAURANT_ID, call_id, "/checkout"),
        json={},
    )
    assert checkout.status_code == 200
    body = checkout.json()
    assert body["status"] == "success"
    order_id = body["order_id"]
    assert body["sms_sent"] is True

    sms_list = await client.get(f"/v1/restaurants/{RESTAURANT_ID}/orders/{order_id}/sms")
    assert sms_list.status_code == 200
    assert len(sms_list.json()["messages"]) >= 1
    assert sms_list.json()["messages"][0]["body"] == body["sms_summary"]

    pay = await client.post(
        f"/v1/restaurants/{RESTAURANT_ID}/orders/{order_id}/payment",
        json={
            "card_number": "4111111111111111",
            "exp_month": 12,
            "exp_year": 2030,
            "cvv": "123",
        },
    )
    assert pay.status_code == 200
    assert pay.json()["status"] == "succeeded"

    payments = await client.get(f"/v1/restaurants/{RESTAURANT_ID}/orders/{order_id}/payments")
    assert payments.status_code == 200
    assert len(payments.json()["payments"]) == 1
    assert payments.json()["payments"][0]["last_four"] == "1111"
    assert payments.json()["payments"][0]["amount_cents"] == body["cart"]["total_cents"]

    await close_database()
    os.environ["DATABASE_URL"] = ""
    get_settings.cache_clear()
    init_database()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("INTEGRATION_DB"),
    reason="Set INTEGRATION_DB=1 to verify restaurant seed rows",
)
async def test_restaurants_seeded_in_postgres() -> None:
    os.environ.pop("DATABASE_URL", None)
    get_settings.cache_clear()
    init_database()

    if not get_settings().database_enabled or not await check_database():
        pytest.skip("DATABASE_URL not configured or database unreachable")

    from sqlalchemy import select

    from apps.order_api.db.engine import get_db_session
    from apps.order_api.db.models import RestaurantRow
    from apps.order_api.db.seed import sync_restaurants_from_config
    from apps.order_api.use_cases import use_cases

    await sync_restaurants_from_config(use_cases.config_root())
    async with get_db_session() as session:
        result = await session.execute(select(RestaurantRow.id))
        ids = {row[0] for row in result.all()}
    assert "hot_bagels_2nd_street" in ids
    assert "demo_cafe" in ids

    await close_database()
    os.environ["DATABASE_URL"] = ""
    get_settings.cache_clear()
    init_database()
