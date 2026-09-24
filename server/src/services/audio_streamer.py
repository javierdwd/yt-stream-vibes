"""YouTube Live audio → Faster-Whisper transcript → JEV streamer vibe."""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
import time
from collections.abc import AsyncIterator
from typing import Any

import numpy as np
from typesafe_sdk import AsyncTypeSafeClient

from src.services.jev_classifier import (
    VIBE_AXES,
    classify_batch,
    empty_vibe_counts,
)

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16_000
_CHUNK_SECONDS = 5.0
_CHUNK_BYTES = int(_SAMPLE_RATE * 2 * _CHUNK_SECONDS)  # s16le mono
_MIN_TRANSCRIPT_CHARS = 3

_whisper_model: Any | None = None
_whisper_lock = asyncio.Lock()


def _env(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


def youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def audio_prereqs() -> str | None:
    """Return an error string if ffmpeg/yt-dlp are missing, else None."""
    missing: list[str] = []
    if shutil.which("ffmpeg") is None:
        missing.append("ffmpeg")
    if shutil.which("yt-dlp") is None:
        missing.append("yt-dlp")
    if missing:
        return f"missing system deps: {', '.join(missing)}"
    return None


async def _get_whisper_model() -> Any:
    global _whisper_model
    async with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model

        def _load() -> Any:
            from faster_whisper import WhisperModel

            model_size = _env("WHISPER_MODEL", "tiny")
            device = _env("WHISPER_DEVICE", "cpu")
            compute = _env("WHISPER_COMPUTE_TYPE", "int8")
            logger.info(
                "Loading Faster-Whisper model=%s device=%s compute=%s",
                model_size,
                device,
                compute,
            )
            return WhisperModel(model_size, device=device, compute_type=compute)

        _whisper_model = await asyncio.to_thread(_load)
        return _whisper_model


def _pcm_s16le_to_float32(pcm: bytes) -> np.ndarray:
    if not pcm:
        return np.zeros(0, dtype=np.float32)
    audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


def _transcribe_pcm(model: Any, pcm: bytes) -> str:
    audio = _pcm_s16le_to_float32(pcm)
    if audio.size < _SAMPLE_RATE * 0.4:
        return ""
    # Skip near-silent chunks (cheap RMS gate).
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    if rms < 0.008:
        return ""
    segments, _info = model.transcribe(
        audio,
        language=None,
        vad_filter=True,
        beam_size=1,
    )
    parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
    return " ".join(parts).strip()


async def _read_exact(stream: asyncio.StreamReader, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = await stream.read(n - len(buf))
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


async def _kill_process(proc: asyncio.subprocess.Process | None) -> None:
    if proc is None or proc.returncode is not None:
        return
    try:
        proc.kill()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=3.0)
    except (asyncio.TimeoutError, ProcessLookupError):
        pass


async def iter_pcm_chunks(
    video_id: str,
    stop_event: asyncio.Event,
) -> AsyncIterator[bytes]:
    """Yield 5s s16le mono PCM chunks from a YouTube Live stream."""
    url = youtube_watch_url(video_id)
    # One shell pipeline: asyncio cannot pass StreamReader as another process's stdin
    # (no fileno). yt-dlp audio → ffmpeg 16k mono s16le on stdout.
    pipeline = (
        f"yt-dlp -f bestaudio/best -o - --no-playlist --quiet --no-warnings "
        f"{shlex.quote(url)} "
        f"| ffmpeg -hide_banner -loglevel error -i pipe:0 "
        f"-f s16le -ac 1 -ar {_SAMPLE_RATE} pipe:1"
    )

    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_shell(
            pipeline,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert proc.stdout is not None

        while not stop_event.is_set():
            try:
                pcm = await asyncio.wait_for(
                    _read_exact(proc.stdout, _CHUNK_BYTES),
                    timeout=_CHUNK_SECONDS + 15.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Audio chunk read timed out video=%s", video_id)
                break
            if len(pcm) < _CHUNK_BYTES // 2:
                break
            if len(pcm) < _CHUNK_BYTES:
                # Pad short final/partial chunk so Whisper still gets a buffer.
                pcm = pcm + b"\x00" * (_CHUNK_BYTES - len(pcm))
            yield pcm
    finally:
        await _kill_process(proc)


async def iter_streamer_events(
    video_id: str,
    stop_event: asyncio.Event,
    *,
    client: AsyncTypeSafeClient,
) -> AsyncIterator[dict[str, Any]]:
    """Transcribe + JEV-classify live audio. Soft-fails via raised errors to caller."""
    prereq = audio_prereqs()
    if prereq:
        raise RuntimeError(prereq)

    model = await _get_whisper_model()

    async for pcm in iter_pcm_chunks(video_id, stop_event):
        if stop_event.is_set():
            break

        t0 = time.perf_counter()
        try:
            transcript = await asyncio.to_thread(_transcribe_pcm, model, pcm)
        except Exception:
            logger.exception("Whisper transcribe failed video=%s", video_id)
            continue

        if len(transcript) < _MIN_TRANSCRIPT_CHARS:
            continue

        msg = {
            "id": f"streamer-{int(time.time() * 1000)}",
            "author": "streamer",
            "message": transcript,
        }
        try:
            metrics = await classify_batch([msg], client=client)
        except Exception:
            logger.exception("JEV streamer classify failed video=%s", video_id)
            continue

        classifications = metrics.get("classifications") or []
        item = classifications[0] if classifications else {}
        vibe = item.get("vibe")
        counts = empty_vibe_counts()
        if vibe in counts:
            counts[vibe] = 1

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "Streamer audio video=%s chars=%d vibe=%s elapsed_ms=%.0f",
            video_id,
            len(transcript),
            vibe,
            elapsed_ms,
        )
        yield {
            "ts": time.monotonic(),
            "transcript": transcript,
            "streamer_vibe": vibe if vibe in VIBE_AXES else None,
            "streamer_vibe_counts": counts,
        }
