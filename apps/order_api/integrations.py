from __future__ import annotations

import httpx

from apps.payment_service.processor import default_processor
from apps.payment_service.schemas import ChargeRequest, ChargeResponse
from apps.sms_gateway.schemas import SendSmsRequest, SendSmsResponse
from apps.sms_gateway.sender import default_sender


async def charge_payment(
    base_url: str,
    request: ChargeRequest,
) -> ChargeResponse:
    if not base_url:
        return default_processor.charge(request)
    async with httpx.AsyncClient(timeout=15.0) as client:
        url = f"{base_url.rstrip('/')}/v1/charges"
        response = await client.post(url, json=request.model_dump())
        response.raise_for_status()
        return ChargeResponse.model_validate(response.json())


async def send_order_sms(
    base_url: str,
    request: SendSmsRequest,
) -> SendSmsResponse:
    if not base_url:
        return default_sender.send(request)
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(f"{base_url.rstrip('/')}/v1/send", json=request.model_dump())
        response.raise_for_status()
        return SendSmsResponse.model_validate(response.json())
