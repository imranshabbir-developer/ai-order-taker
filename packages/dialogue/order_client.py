from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class ToolResponse:
    status: str
    message: str
    line_id: str | None = None
    options: list[str] | None = None
    cart: dict[str, Any] | None = None
    spoken_summary: str | None = None
    sms_summary: str | None = None
    order_id: str | None = None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> ToolResponse:
        return cls(
            status=str(payload.get("status", "")),
            message=str(payload.get("message", "")),
            line_id=payload.get("line_id"),
            options=list(payload.get("options") or []),
            cart=payload.get("cart"),
            spoken_summary=payload.get("spoken_summary"),
            sms_summary=payload.get("sms_summary"),
            order_id=payload.get("order_id"),
        )


class OrderApiClient:
    """HTTP adapter for the Order API tool endpoint."""

    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _call_path(self, restaurant_id: str, call_id: str) -> str:
        return f"/v1/restaurants/{restaurant_id}/calls/{call_id}"

    async def reset_call(self, restaurant_id: str, call_id: str) -> None:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            response = await client.post(f"{self._call_path(restaurant_id, call_id)}/reset")
            response.raise_for_status()

    async def start_call(
        self, restaurant_id: str, call_id: str, caller_phone: str = ""
    ) -> dict[str, Any]:
        payload = {"caller_phone": caller_phone} if caller_phone else {}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            response = await client.post(
                f"{self._call_path(restaurant_id, call_id)}/start",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def capture_payment(
        self,
        restaurant_id: str,
        order_id: str,
        *,
        card_number: str,
        exp_month: int,
        exp_year: int,
        cvv: str,
        call_id: str = "",
    ) -> dict[str, Any]:
        params = {"call_id": call_id} if call_id else {}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            response = await client.post(
                f"/v1/restaurants/{restaurant_id}/orders/{order_id}/payment",
                params=params,
                json={
                    "card_number": card_number,
                    "exp_month": exp_month,
                    "exp_year": exp_year,
                    "cvv": cvv,
                },
            )
            response.raise_for_status()
            return response.json()

    async def invoke_tool(
        self,
        restaurant_id: str,
        call_id: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
    ) -> ToolResponse:
        payload = {"tool": tool, "arguments": arguments or {}}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            response = await client.post(
                f"{self._call_path(restaurant_id, call_id)}/tool",
                json=payload,
            )
            response.raise_for_status()
            return ToolResponse.from_api(response.json())

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            response = await client.get("/health")
            response.raise_for_status()
            return response.json()
