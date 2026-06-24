from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.voice_agent.server import app


@pytest.mark.asyncio
async def test_voice_server_health() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["service"] == "voice_agent"


@pytest.mark.asyncio
async def test_voice_server_index() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "Hot Bagels Voice Test" in response.text
