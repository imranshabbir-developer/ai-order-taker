"""Start mock payment service on port 8002."""

from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    print("Payment service: http://127.0.0.1:8002")
    uvicorn.run("apps.payment_service.main:app", host="127.0.0.1", port=8002, reload=True)
