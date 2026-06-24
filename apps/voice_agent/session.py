from __future__ import annotations

import base64
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dialogue.agent import AgentTurnResult, DialogueAgent
from dialogue.llm import LLMClient, OpenAICompatibleLLM
from dialogue.order_client import OrderApiClient
from dialogue.prompts import load_prompts
from dialogue.settings import get_dialogue_settings

from apps.voice_agent.latency import LatencyLogger
from apps.voice_agent.providers import STTProvider, load_catalog
from apps.voice_agent.providers.stt import GroqWhisperSTT
from apps.voice_agent.providers.tts import EdgeTTSProvider, TextTTSProvider, play_audio
from apps.voice_agent.settings import VoiceSettings, get_voice_settings
from apps.voice_agent.transcript import load_pronunciations, normalize_transcript


@dataclass
class VoiceTurnResult:
    transcript: str
    normalized_transcript: str
    agent: AgentTurnResult
    audio_path: Path | None = None
    audio_base64: str | None = None
    latency_ms: dict[str, float] = field(default_factory=dict)


class VoiceOrderSession:
    """Voice I/O wrapper around the Sprint 3 DialogueAgent."""

    def __init__(
        self,
        *,
        restaurant_id: str | None = None,
        call_id: str | None = None,
        llm: LLMClient | None = None,
        stt: STTProvider | None = None,
        tts: EdgeTTSProvider | TextTTSProvider | None = None,
        voice_settings: VoiceSettings | None = None,
        output_dir: Path | None = None,
        latency_logger: LatencyLogger | None = None,
        local_playback: bool = True,
    ) -> None:
        self._voice_settings = voice_settings or get_voice_settings()
        self._dialogue_settings = get_dialogue_settings()
        self._restaurant_id = restaurant_id or self._voice_settings.default_restaurant_id
        self._call_id = call_id or f"voice-{uuid.uuid4().hex[:10]}"
        self._output_dir = output_dir or Path("output/voice") / self._call_id
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._latency = latency_logger or LatencyLogger()
        self._local_playback = local_playback
        self._busy = False
        self._turn_counter = 0

        order_client = OrderApiClient(self._dialogue_settings.order_api_base_url)
        if llm is not None:
            llm_client = llm
        elif self._voice_settings.voice_llm_base_url.strip():
            llm_client = OpenAICompatibleLLM(
                base_url=self._voice_settings.voice_llm_base_url,
                model=self._voice_settings.voice_llm_model,
                api_key=self._voice_settings.voice_llm_api_key
                or self._voice_settings.effective_stt_api_key,
                timeout=self._dialogue_settings.llm_timeout_seconds,
            )
        else:
            llm_client = OpenAICompatibleLLM(
                base_url=self._dialogue_settings.llm_base_url,
                model=self._dialogue_settings.llm_model,
                api_key=self._dialogue_settings.llm_api_key,
                timeout=self._dialogue_settings.llm_timeout_seconds,
            )
        prompts = load_prompts(self._restaurant_id)
        self._agent = DialogueAgent(
            llm_client,
            order_client,
            prompts,
            self._restaurant_id,
            self._call_id,
            max_tool_rounds=self._dialogue_settings.llm_max_tool_rounds,
        )
        self._stt = stt or GroqWhisperSTT(self._voice_settings)
        if tts is not None:
            self._tts = tts
        elif self._voice_settings.tts_enabled:
            self._tts = EdgeTTSProvider(self._voice_settings)
        else:
            self._tts = TextTTSProvider()

        self._catalog = load_catalog(self._restaurant_id)
        self._pronunciations = load_pronunciations(self._restaurant_id)

    @property
    def call_id(self) -> str:
        return self._call_id

    @property
    def restaurant_id(self) -> str:
        return self._restaurant_id

    def to_web_payload(self, turn: VoiceTurnResult, *, event: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": event,
            "call_id": self._call_id,
            "transcript": turn.transcript,
            "normalized_transcript": turn.normalized_transcript,
            "assistant_message": turn.agent.assistant_message,
            "phase": turn.agent.phase.value,
            "done": turn.agent.done,
            "latency_ms": turn.latency_ms,
        }
        if turn.agent.tool_results:
            last = turn.agent.tool_results[-1]
            payload["engine_status"] = last.status
            payload["engine_message"] = last.message
        if turn.audio_base64:
            payload["audio_base64"] = turn.audio_base64
            payload["audio_mime"] = "audio/mpeg"
        return payload

    async def start(self) -> VoiceTurnResult:
        t0 = time.perf_counter()
        start = await self._agent.start()
        audio_path, audio_b64 = None, None
        if start.assistant_message:
            audio_path, audio_b64 = await self._synthesize(start.assistant_message, tag="greeting")
        turn = VoiceTurnResult(
            transcript="",
            normalized_transcript="",
            agent=start,
            audio_path=audio_path,
            audio_base64=audio_b64,
            latency_ms={"total": (time.perf_counter() - t0) * 1000},
        )
        self._log_turn("greeting", turn)
        return turn

    async def process_text(self, user_text: str, *, speak: bool = True) -> VoiceTurnResult:
        if self._busy:
            user_text = f"[interrupt] {user_text}"
        self._busy = True
        try:
            t0 = time.perf_counter()
            normalized = normalize_transcript(
                user_text,
                self._catalog,
                pronunciation_aliases=self._pronunciations,
            )
            t_agent = time.perf_counter()
            agent_result = await self._agent.handle_user_message(normalized)
            agent_ms = (time.perf_counter() - t_agent) * 1000

            audio_path, audio_b64 = None, None
            tts_ms = 0.0
            if speak and agent_result.assistant_message:
                t_tts = time.perf_counter()
                audio_path, audio_b64 = await self._synthesize(
                    agent_result.assistant_message,
                    tag=f"reply-{self._turn_counter}",
                )
                tts_ms = (time.perf_counter() - t_tts) * 1000
                self._turn_counter += 1

            turn = VoiceTurnResult(
                transcript=user_text,
                normalized_transcript=normalized,
                agent=agent_result,
                audio_path=audio_path,
                audio_base64=audio_b64,
                latency_ms={
                    "agent": agent_ms,
                    "tts": tts_ms,
                    "total": (time.perf_counter() - t0) * 1000,
                },
            )
            self._log_turn("turn", turn)
            return turn
        finally:
            self._busy = False

    async def process_audio_bytes(
        self, audio_bytes: bytes, *, suffix: str = ".wav", speak: bool = True
    ) -> VoiceTurnResult:
        t0 = time.perf_counter()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            audio_path = Path(tmp.name)
        try:
            transcript = await self._stt.transcribe(audio_path)
        finally:
            audio_path.unlink(missing_ok=True)
        stt_ms = (time.perf_counter() - t0) * 1000
        result = await self.process_text(transcript, speak=speak)
        result.latency_ms["stt"] = stt_ms
        result.latency_ms["total"] = (time.perf_counter() - t0) * 1000
        self._log_turn("audio_turn", result)
        return result

    async def process_audio(self, audio_path: Path, *, speak: bool = True) -> VoiceTurnResult:
        return await self.process_audio_bytes(
            audio_path.read_bytes(),
            suffix=audio_path.suffix or ".wav",
            speak=speak,
        )

    async def _synthesize(self, text: str, *, tag: str) -> tuple[Path | None, str | None]:
        path = self._output_dir / f"{tag}.mp3"
        await self._tts.synthesize(text, path)
        audio_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        if self._local_playback and self._voice_settings.tts_enabled:
            play_audio(path)
        return path, audio_b64

    def _log_turn(self, event: str, turn: VoiceTurnResult) -> None:
        self._latency.log(
            call_id=self._call_id,
            event=event,
            latency_ms=turn.latency_ms,
            extra={
                "phase": turn.agent.phase.value,
                "engine_status": turn.agent.tool_results[-1].status
                if turn.agent.tool_results
                else None,
            },
        )
