"""YouTube Live audio → Faster-Whisper transcript (vibe/alignment downstream)."""

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

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16_000
_CHUNK_SECONDS = 3.0
_CHUNK_BYTES = int(_SAMPLE_RATE * 2 * _CHUNK_SECONDS)  # s16le mono
_MIN_TRANSCRIPT_CHARS = 3

_whisper_model: Any | None = None
_whisper_lock = asyncio.Lock()


def _env(name: str, default: str) -> str:
    return (os.getenv(name) or default).strip()


def youtube_watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def writable_cookie_file(src: str) -> str | None:
    """Copy a (possibly read-only) Netscape cookie file to a writable path.

    yt-dlp writes cookies back on exit; Docker mounts are often :ro.
    """
    if not src or not os.path.isfile(src):
        return None
    cache = _env("XDG_CACHE_HOME", "/tmp")
    dest = os.path.join(cache or "/tmp", "youtube-cookies.writable.txt")
    try:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        shutil.copyfile(src, dest)
        return dest
    except OSError:
        dest = "/tmp/youtube-cookies.writable.txt"
        try:
            shutil.copyfile(src, dest)
            return dest
        except OSError:
            logger.warning("Could not copy YTDLP_COOKIES to a writable path")
            return None


def _ytdlp_auth_args() -> str:
    """Optional yt-dlp auth so YouTube bot checks don't kill the audio pipe.

    Set one of:
      YTDLP_COOKIES_FROM_BROWSER=chrome|safari|firefox|brave|edge  (local only)
      YTDLP_COOKIES=/absolute/path/to/cookies.txt  (AWS/Docker)
    """
    browser = _env("YTDLP_COOKIES_FROM_BROWSER", "")
    if browser:
        return f"--cookies-from-browser {shlex.quote(browser)} "
    cookies = _env("YTDLP_COOKIES", "")
    if cookies:
        writable = writable_cookie_file(cookies)
        if writable is None:
            logger.warning(
                "YTDLP_COOKIES=%s not found — YouTube STT will likely fail "
                "on datacenter IPs. Export cookies locally and mount the file.",
                cookies,
            )
            return ""
        return f"--cookies {shlex.quote(writable)} "
    logger.warning(
        "No YTDLP_COOKIES / YTDLP_COOKIES_FROM_BROWSER set — "
        "YouTube may block yt-dlp audio on AWS"
    )
    return ""


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
    """Yield s16le mono PCM chunks from a YouTube Live stream."""
    url = youtube_watch_url(video_id)
    auth = _ytdlp_auth_args()
    # One shell pipeline: asyncio cannot pass StreamReader as another process's stdin
    # (no fileno). yt-dlp audio → ffmpeg 16k mono s16le on stdout.
    pipeline = (
        f"yt-dlp -f bestaudio/best -o - --no-playlist --quiet --no-warnings "
        f"{auth}{shlex.quote(url)} "
        f"| ffmpeg -hide_banner -loglevel error -i pipe:0 "
        f"-f s16le -ac 1 -ar {_SAMPLE_RATE} pipe:1"
    )

    proc: asyncio.subprocess.Process | None = None
    stderr_task: asyncio.Task[None] | None = None
    try:
        proc = await asyncio.create_subprocess_shell(
            pipeline,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert proc.stdout is not None
        assert proc.stderr is not None

        async def _drain_stderr() -> None:
            assert proc is not None and proc.stderr is not None
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                msg = line.decode("utf-8", errors="replace").strip()
                if msg:
                    logger.warning("yt-dlp/ffmpeg video=%s: %s", video_id, msg)

        stderr_task = asyncio.create_task(_drain_stderr())

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
        if stderr_task is not None:
            stderr_task.cancel()
            try:
                await stderr_task
            except asyncio.CancelledError:
                pass


async def iter_streamer_events(
    video_id: str,
    stop_event: asyncio.Event,
) -> AsyncIterator[dict[str, Any]]:
    """Yield transcripts as soon as Whisper finishes (vibe/alignment happen downstream)."""
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

        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "Streamer audio video=%s chars=%d whisper_ms=%.0f",
            video_id,
            len(transcript),
            elapsed_ms,
        )
        yield {
            "ts": time.monotonic(),
            "transcript": transcript,
        }
