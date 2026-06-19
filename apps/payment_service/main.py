from __future__ import annotations

from fastapi import FastAPI

from apps.payment_service.processor import default_processor
from apps.payment_service.schemas import ChargeRequest, ChargeResponse

app = FastAPI(
    title="Restaurants AI Agent — Payment Service",
    version="0.1.0",
    description="Isolated card capture — LLM and voice logs never receive raw PAN/CVV.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "payment_service"}


@app.post("/v1/charges", response_model=ChargeResponse)
async def create_charge(body: ChargeRequest) -> ChargeResponse:
    return default_processor.charge(body)


@app.get("/v1/charges/{charge_id}")
async def get_charge(charge_id: str) -> dict:
    record = default_processor.charges.get(charge_id)
    if record is None:
        return {"status": "not_found"}
    return {
        "charge_id": record.charge_id,
        "order_id": record.order_id,
        "amount_cents": record.amount_cents,
        "last_four": record.last_four,
        "status": record.status,
    }
