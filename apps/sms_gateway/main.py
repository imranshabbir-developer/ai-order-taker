from __future__ import annotations

from fastapi import FastAPI

from apps.sms_gateway.schemas import SendSmsRequest, SendSmsResponse
from apps.sms_gateway.sender import default_sender

app = FastAPI(
    title="Restaurants AI Agent — SMS Gateway",
    version="0.1.0",
    description="Sends order confirmation SMS from Cart.to_sms_summary() text.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "sms_gateway"}


@app.post("/v1/send", response_model=SendSmsResponse)
async def send_sms(body: SendSmsRequest) -> SendSmsResponse:
    return default_sender.send(body)


@app.get("/v1/messages/{sms_id}")
async def get_message(sms_id: str) -> dict:
    record = default_sender.messages.get(sms_id)
    if record is None:
        return {"status": "not_found"}
    return {
        "sms_id": record.sms_id,
        "order_id": record.order_id,
        "to_phone": record.to_phone,
        "body": record.body,
        "status": record.status,
        "restaurant_id": record.restaurant_id,
    }
