"""Start mock SMS gateway on port 8003."""

from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    print("SMS gateway: http://127.0.0.1:8003")
    uvicorn.run("apps.sms_gateway.main:app", host="127.0.0.1", port=8003, reload=True)
