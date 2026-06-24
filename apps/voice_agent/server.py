from __future__ import annotations

import base64
import json
import uuid
from pathlib import Path
from typing import Any

from dialogue.settings import get_dialogue_settings
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from apps.voice_agent.session import VoiceOrderSession
from apps.voice_agent.settings import get_voice_settings

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Restaurants AI Agent — Voice Server",
    version="0.1.0",
    description="WebSocket + browser client for voice ordering (Sprint 4.7).",
)

_sessions: dict[str, VoiceOrderSession] = {}


class VoiceTurnRequest(BaseModel):
    text: str = ""
    audio_base64: str = ""
    restaurant_id: str = "hot_bagels_2nd_street"


class VoiceStartResponse(BaseModel):
    call_id: str
    greeting: str
    audio_base64: str | None = None
    latency_ms: dict[str, float] = Field(default_factory=dict)


def _get_or_create_session(call_id: str | None, restaurant_id: str) -> VoiceOrderSession:
    cid = call_id or f"voice-{uuid.uuid4().hex[:10]}"
    if cid not in _sessions:
        get_dialogue_settings.cache_clear()
        get_voice_settings.cache_clear()
        _sessions[cid] = VoiceOrderSession(
            restaurant_id=restaurant_id,
            call_id=cid,
            local_playback=False,
        )
    return _sessions[cid]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "voice_agent"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.post("/v1/voice/calls/{call_id}/start", response_model=VoiceStartResponse)
async def start_call(
    call_id: str, restaurant_id: str = "hot_bagels_2nd_street"
) -> VoiceStartResponse:
    session = _get_or_create_session(call_id, restaurant_id)
    turn = await session.start()
    return VoiceStartResponse(
        call_id=session.call_id,
        greeting=turn.agent.assistant_message,
        audio_base64=turn.audio_base64,
        latency_ms=turn.latency_ms,
    )


@app.post("/v1/voice/calls/{call_id}/turn")
async def voice_turn(call_id: str, body: VoiceTurnRequest) -> dict[str, Any]:
    session = _get_or_create_session(call_id, body.restaurant_id)
    if body.audio_base64:
        audio = base64.b64decode(body.audio_base64)
        turn = await session.process_audio_bytes(audio)
    else:
        turn = await session.process_text(body.text)
    return session.to_web_payload(turn, event="reply")


@app.websocket("/ws/voice/{call_id}")
async def voice_websocket(websocket: WebSocket, call_id: str) -> None:
    await websocket.accept()
    restaurant_id = websocket.query_params.get("restaurant_id", "hot_bagels_2nd_street")
    caller_phone = websocket.query_params.get("caller_phone", "")
    session = _get_or_create_session(call_id, restaurant_id)

    try:
        from dialogue.order_client import OrderApiClient
        from dialogue.settings import get_dialogue_settings

        settings = get_dialogue_settings()
        if caller_phone:
            client = OrderApiClient(settings.order_api_base_url)
            await client.start_call(restaurant_id, session.call_id, caller_phone)
        greeting = await session.start()
        await websocket.send_text(json.dumps(session.to_web_payload(greeting, event="greeting")))

        while True:
            raw = await websocket.receive_text()
            message = json.loads(raw)
            msg_type = message.get("type", "text")

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if msg_type == "interrupt":
                session._busy = False
                await websocket.send_text(json.dumps({"type": "interrupted"}))
                continue

            if msg_type == "audio":
                audio = base64.b64decode(message.get("data", ""))
                turn = await session.process_audio_bytes(audio)
            else:
                text = str(message.get("text", message.get("content", "")))
                turn = await session.process_text(text)

            await websocket.send_text(json.dumps(session.to_web_payload(turn, event="reply")))
            if turn.agent.done:
                break
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": str(exc),
                        "hint": (
                            "Check Order API is running and ORDER_API_BASE_URL "
                            "matches run_api.py port."
                        ),
                    }
                )
            )
        except Exception:
            pass
        return
