#!/usr/bin/env python3
"""Voice CLI — text or audio file → dialogue agent → spoken reply."""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dialogue.settings import get_dialogue_settings  # noqa: E402

from apps.voice_agent.providers.tts import TextTTSProvider  # noqa: E402
from apps.voice_agent.session import VoiceOrderSession  # noqa: E402
from apps.voice_agent.settings import get_voice_settings  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Voice order CLI (Sprint 4)")
    parser.add_argument("--text", "-t", help="Process text as if spoken (no microphone)")
    parser.add_argument("--audio", "-a", type=Path, help="Transcribe WAV/audio via Groq Whisper")
    parser.add_argument("--no-speak", action="store_true", help="Skip TTS playback")
    parser.add_argument("--interactive", "-i", action="store_true", help="Type orders in a loop")
    args = parser.parse_args()

    get_dialogue_settings.cache_clear()
    get_voice_settings.cache_clear()

    voice_settings = get_voice_settings()
    if args.no_speak:
        voice_settings.tts_enabled = False

    session = VoiceOrderSession(
        call_id=f"voice-{uuid.uuid4().hex[:8]}",
        tts=TextTTSProvider() if args.no_speak else None,
        local_playback=not args.no_speak,
    )

    try:
        from dialogue.order_client import OrderApiClient  # noqa: PLC0415

        client = OrderApiClient(get_dialogue_settings().order_api_base_url)
        await client.health()
    except Exception as exc:
        print(f"Order API unreachable: {exc}")
        print("Start it first: python run_api.py")
        return 1

    start = await session.start()
    print(f"Agent: {start.agent.assistant_message}\n")

    if args.text:
        turn = await session.process_text(args.text, speak=not args.no_speak)
        _print_turn(turn)
        return 0

    if args.audio:
        if not args.audio.exists():
            print(f"Audio file not found: {args.audio}")
            return 1
        turn = await session.process_audio(args.audio, speak=not args.no_speak)
        _print_turn(turn)
        return 0

    if args.interactive or (not args.text and not args.audio):
        print("Interactive mode — type your order (or 'quit').\n")
        while True:
            try:
                user = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                break
            if not user:
                continue
            if user.lower() in {"quit", "exit", "q"}:
                break
            turn = await session.process_text(user, speak=not args.no_speak)
            _print_turn(turn)
            if turn.agent.done:
                break
        return 0

    parser.print_help()
    return 1


def _print_turn(turn) -> None:
    if turn.transcript:
        print(f"You (heard): {turn.transcript}")
    if turn.normalized_transcript and turn.normalized_transcript != turn.transcript:
        print(f"You (normalized): {turn.normalized_transcript}")
    print(f"Agent: {turn.agent.assistant_message}")
    if turn.agent.tool_results:
        last = turn.agent.tool_results[-1]
        print(f"  engine: {last.status} — {last.message[:100]}")
    if turn.latency_ms:
        parts = ", ".join(f"{k}={v:.0f}ms" for k, v in sorted(turn.latency_ms.items()))
        print(f"  latency: {parts}")
    if turn.audio_path:
        print(f"  audio: {turn.audio_path}")
    print()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
