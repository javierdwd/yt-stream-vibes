"""In-memory analysis sessions: chat pump + JEV, dual chat/stats fanout."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

from typesafe_sdk import AsyncTypeSafeClient

from src.adapters import get_live_adapter
from src.services.alignment_engine import (
    SPEECH_WINDOW_S,
    join_recent_speech,
    recent_chat_lines,
)
from src.services.audio_streamer import iter_streamer_events
from src.services.jev_classifier import (
    VIBE_AXES,
    classify_batch,
    classify_topic_sync,
    empty_vibe_counts,
    radar_from_vibe_counts,
)
from src.services.theme_summarizer import summarize_theme

logger = logging.getLogger(__name__)

_CLASSIFY_QUEUE_SIZE = 8
_SUBSCRIBER_QUEUE_SIZE = 32
Channel = Literal["chat", "stats"]


def enrich_messages(
    batch: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {c["id"]: c for c in classifications if c.get("id")}
    enriched: list[dict[str, Any]] = []
    for msg in batch:
        label = by_id.get(msg.get("id") or "")
        intent = (label or {}).get("intent")
        enriched.append(
            {
                **msg,
                "intent": intent,
                "hype_score": (label or {}).get("hype_score"),
                "vibe": (label or {}).get("vibe"),
                "spam": intent == "spam",
                "spam_reason": "jev" if intent == "spam" else None,
            }
        )
    return enriched


@dataclass
class _WindowSample:
    ts: float
    vibe: str | None
    spam: bool
    hype_score: int


@dataclass
class _ChatSnippet:
    ts: float
    line: str


@dataclass
class AnalysisSession:
    session_id: str
    video_id: str
    platform: str
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    worker: asyncio.Task[None] | None = None
    chat_subs: list[asyncio.Queue[dict[str, Any] | None]] = field(default_factory=list)
    stats_subs: list[asyncio.Queue[dict[str, Any] | None]] = field(default_factory=list)
    window: deque[_WindowSample] = field(default_factory=deque)
    recent_chat: deque[_ChatSnippet] = field(default_factory=deque)
    speech_chunks: deque[tuple[float, str]] = field(default_factory=deque)
    last_stats: dict[str, Any] | None = None
    streamer_transcript: str | None = None
    streamer_vibe: str | None = None
    streamer_vibe_counts: dict[str, int] = field(default_factory=empty_vibe_counts)
    theme_oneliner: str | None = None
    alignment_score: int | None = None
    alignment_label: str | None = None
    audio_error: str | None = None


class SessionRegistry:
    """Process-local session map. Not multi-worker safe (MVP)."""

    def __init__(self) -> None:
        self._sessions: dict[str, AnalysisSession] = {}
        self._lock = asyncio.Lock()

    async def create(self, *, platform: str, stream_id: str) -> AnalysisSession:
        adapter = get_live_adapter(platform)
        session_id = uuid.uuid4().hex
        session = AnalysisSession(
            session_id=session_id,
            video_id=stream_id,
            platform=adapter.platform,
        )
        async with self._lock:
            self._sessions[session_id] = session
        session.worker = asyncio.create_task(
            self._run_session(session),
            name=f"session-{session_id[:8]}",
        )
        logger.info(
            "Session started id=%s platform=%s stream=%s",
            session_id,
            adapter.platform,
            stream_id,
        )
        return session

    def get(self, session_id: str) -> AnalysisSession | None:
        return self._sessions.get(session_id)

    async def stop(self, session_id: str) -> bool:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        session.stop_event.set()
        self._close_all_subs(session)
        if session.worker is not None:
            session.worker.cancel()
            try:
                await session.worker
            except asyncio.CancelledError:
                pass
        logger.info("Session stopped id=%s video=%s", session_id, session.video_id)
        return True

    def subscribe(
        self, session_id: str, channel: Channel
    ) -> asyncio.Queue[dict[str, Any] | None] | None:
        session = self._sessions.get(session_id)
        if session is None or session.stop_event.is_set():
            return None
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(
            maxsize=_SUBSCRIBER_QUEUE_SIZE
        )
        if channel == "chat":
            session.chat_subs.append(q)
        else:
            session.stats_subs.append(q)
            if session.last_stats is not None:
                self._put_drop_oldest(q, session.last_stats)
        return q

    def unsubscribe(
        self,
        session_id: str,
        channel: Channel,
        q: asyncio.Queue[dict[str, Any] | None],
    ) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        subs = session.chat_subs if channel == "chat" else session.stats_subs
        try:
            subs.remove(q)
        except ValueError:
            pass

    def _close_all_subs(self, session: AnalysisSession) -> None:
        for q in list(session.chat_subs) + list(session.stats_subs):
            self._put_drop_oldest(q, None)
        session.chat_subs.clear()
        session.stats_subs.clear()

    @staticmethod
    def _put_drop_oldest(
        q: asyncio.Queue[dict[str, Any] | None], item: dict[str, Any] | None
    ) -> None:
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            pass

    def _fanout(
        self,
        session: AnalysisSession,
        channel: Channel,
        payload: dict[str, Any],
    ) -> None:
        subs = session.chat_subs if channel == "chat" else session.stats_subs
        for q in list(subs):
            self._put_drop_oldest(q, payload)

    def _prune_sync_buffers(self, session: AnalysisSession, now: float) -> None:
        speech_cut = now - SPEECH_WINDOW_S - 5.0
        while session.speech_chunks and session.speech_chunks[0][0] < speech_cut:
            session.speech_chunks.popleft()
        chat_cut = now - SPEECH_WINDOW_S - 5.0
        while session.recent_chat and session.recent_chat[0].ts < chat_cut:
            session.recent_chat.popleft()

    async def _refresh_topic_alignment(
        self,
        session: AnalysisSession,
        client: AsyncTypeSafeClient,
        now: float,
    ) -> None:
        self._prune_sync_buffers(session, now)
        speech = join_recent_speech(list(session.speech_chunks), now=now)
        chat_lines = recent_chat_lines(list(session.recent_chat), now=now)
        # Do not overwrite streamer_transcript here — UI shows the latest chunk only.
        if not speech or not chat_lines:
            return
        try:
            result = await classify_topic_sync(
                streamer_speech=speech,
                chat_lines=chat_lines,
                client=client,
            )
        except Exception:
            logger.exception(
                "Topic sync classify failed session=%s", session.session_id
            )
            result = {"skipped": True}
        if not result.get("skipped"):
            session.alignment_score = result.get("alignment_score")
            session.alignment_label = result.get("alignment_label")

        try:
            theme = await summarize_theme(
                streamer_speech=speech,
                chat_lines=chat_lines,
            )
            if theme:
                session.theme_oneliner = theme
        except Exception:
            logger.exception(
                "Theme summarize failed session=%s", session.session_id
            )

    def _ingest_classifications(
        self,
        session: AnalysisSession,
        classifications: list[dict[str, Any]],
        now: float,
    ) -> None:
        for item in classifications:
            spam = item.get("intent") == "spam"
            # Session-scoped: keep every classified message until Clear/stop.
            session.window.append(
                _WindowSample(
                    ts=now,
                    vibe=None if spam else item.get("vibe"),
                    spam=spam,
                    hype_score=0 if spam else int(item.get("hype_score") or 0),
                )
            )
            if spam:
                continue
            text = (item.get("message") or "").strip()
            if not text:
                continue
            author = (item.get("author") or "").strip() or "anon"
            session.recent_chat.append(
                _ChatSnippet(ts=now, line=f"{author}: {text}")
            )
        self._prune_sync_buffers(session, now)

    def _stats_snapshot(self, session: AnalysisSession, now: float) -> dict[str, Any]:
        vibe_counts = empty_vibe_counts()
        hype_values: list[int] = []
        spam_count = 0
        oldest_ts: float | None = None
        newest_ts: float | None = None
        for sample in session.window:
            oldest_ts = sample.ts if oldest_ts is None else oldest_ts
            newest_ts = sample.ts
            if sample.spam:
                spam_count += 1
                continue
            if sample.vibe in vibe_counts:
                vibe_counts[sample.vibe] += 1
            hype_values.append(sample.hype_score)

        message_count = len(session.window)
        non_spam = message_count - spam_count
        avg_hype = int(round(sum(hype_values) / len(hype_values))) if hype_values else 0
        spam_rate = (spam_count / message_count) if message_count else 0.0
        radar = radar_from_vibe_counts(vibe_counts)
        span_s = (
            int(max(0.0, (newest_ts or now) - (oldest_ts or now)))
            if message_count
            else 0
        )

        payload: dict[str, Any] = {
            "session_id": session.session_id,
            "video_id": session.video_id,
            "platform": session.platform,
            "hype_score": avg_hype,
            "spam_rate": round(spam_rate, 4),
            "spam_count": spam_count,
            "window": {
                "message_count": message_count,
                "non_spam_count": non_spam,
                "span_seconds": span_s,
            },
            "streamer_transcript": session.streamer_transcript,
            "streamer_vibe": session.streamer_vibe,
            "theme_oneliner": session.theme_oneliner,
            "alignment_score": session.alignment_score,
            "alignment_label": session.alignment_label,
            **radar,
        }
        if session.audio_error:
            payload["audio_error"] = session.audio_error
        return payload

    def _publish_stats(self, session: AnalysisSession, now: float, **extra: Any) -> None:
        stats = self._stats_snapshot(session, now)
        stats.update(extra)
        session.last_stats = stats
        self._fanout(session, "stats", stats)

    async def _run_session(self, session: AnalysisSession) -> None:
        adapter = get_live_adapter(session.platform)
        pending: asyncio.Queue[list[dict[str, Any]] | None] = asyncio.Queue(
            maxsize=_CLASSIFY_QUEUE_SIZE
        )

        async def pump_chat() -> None:
            try:
                async for batch in adapter.stream_chat_batches(
                    session.video_id, flush_interval_s=3.0
                ):
                    if session.stop_event.is_set():
                        break
                    if not batch:
                        continue
                    if pending.full():
                        try:
                            dropped = pending.get_nowait()
                            logger.warning(
                                "Dropped stale chat batch (%d msgs) session=%s",
                                len(dropped or []),
                                session.session_id,
                            )
                        except asyncio.QueueEmpty:
                            pass
                    await pending.put(batch)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Chat pump failed session=%s", session.session_id)
            finally:
                try:
                    pending.put_nowait(None)
                except asyncio.QueueFull:
                    try:
                        pending.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        pending.put_nowait(None)
                    except asyncio.QueueFull:
                        pass

        async def pump_audio() -> None:
            if session.platform != "youtube":
                return
            followup_task: asyncio.Task[None] | None = None

            async def _vibe_and_align(
                transcript: str,
                chunk_ts: float,
                client: AsyncTypeSafeClient,
            ) -> None:
                """JEV vibe + topic/theme — off the Whisper hot path."""
                if session.stop_event.is_set():
                    return
                msg = {
                    "id": f"streamer-{int(chunk_ts * 1000)}",
                    "author": "streamer",
                    "message": transcript,
                }
                try:
                    metrics = await classify_batch([msg], client=client)
                    item = (metrics.get("classifications") or [None])[0] or {}
                    vibe = item.get("vibe")
                    counts = empty_vibe_counts()
                    if vibe in counts:
                        counts[vibe] = 1
                    session.streamer_vibe = vibe if vibe in VIBE_AXES else None
                    session.streamer_vibe_counts = counts
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "JEV streamer classify failed session=%s",
                        session.session_id,
                    )
                try:
                    await self._refresh_topic_alignment(session, client, chunk_ts)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception(
                        "Alignment followup failed session=%s",
                        session.session_id,
                    )
                self._publish_stats(session, time.monotonic())

            try:
                async with AsyncTypeSafeClient() as audio_client:
                    async for event in iter_streamer_events(
                        session.video_id,
                        session.stop_event,
                    ):
                        if session.stop_event.is_set():
                            break
                        session.audio_error = None
                        now = float(event.get("ts") or time.monotonic())
                        transcript = (event.get("transcript") or "").strip()
                        if not transcript:
                            continue
                        session.speech_chunks.append((now, transcript))
                        self._prune_sync_buffers(session, now)
                        # UX: latest chunk only (not the 20s join — that lags line-clamp).
                        session.streamer_transcript = transcript
                        self._publish_stats(session, now)

                        if followup_task is not None and not followup_task.done():
                            followup_task.cancel()
                        followup_task = asyncio.create_task(
                            _vibe_and_align(transcript, now, audio_client),
                            name=f"audio-followup-{session.session_id[:8]}",
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception(
                    "Audio pump failed session=%s video=%s",
                    session.session_id,
                    session.video_id,
                )
                session.audio_error = str(exc)[:240]
                self._publish_stats(session, time.monotonic())
            finally:
                if followup_task is not None and not followup_task.done():
                    followup_task.cancel()
                    await asyncio.gather(followup_task, return_exceptions=True)

        pump = asyncio.create_task(
            pump_chat(), name=f"chat-pump-{session.session_id[:8]}"
        )
        audio_task = asyncio.create_task(
            pump_audio(), name=f"audio-pump-{session.session_id[:8]}"
        )
        try:
            async with AsyncTypeSafeClient() as client:
                while not session.stop_event.is_set():
                    try:
                        batch = await asyncio.wait_for(pending.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    if batch is None:
                        break

                    metrics: dict[str, Any] = {
                        "classifications": [],
                        "hype_score": 0,
                    }
                    t0 = time.perf_counter()
                    try:
                        metrics = await classify_batch(batch, client=client)
                    except Exception:
                        logger.exception(
                            "JEV classify failed session=%s", session.session_id
                        )
                        metrics = {**metrics, "error": "classify_failed"}
                    elapsed_ms = (time.perf_counter() - t0) * 1000
                    logger.info(
                        "JEV batch session=%s video=%s msgs=%d elapsed_ms=%.0f",
                        session.session_id,
                        session.video_id,
                        len(batch),
                        elapsed_ms,
                    )

                    now = time.monotonic()
                    classifications = metrics.get("classifications") or []
                    if not metrics.get("error"):
                        self._ingest_classifications(session, classifications, now)

                    chat_payload: dict[str, Any] = {
                        "session_id": session.session_id,
                        "video_id": session.video_id,
                        "platform": session.platform,
                        "messages": enrich_messages(batch, classifications),
                    }
                    if metrics.get("error"):
                        chat_payload["classify_error"] = metrics["error"]
                    self._fanout(session, "chat", chat_payload)

                    extra: dict[str, Any] = {}
                    if metrics.get("error"):
                        extra["classify_error"] = metrics["error"]
                    self._publish_stats(session, now, **extra)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Session worker crashed id=%s", session.session_id)
            err = {
                "session_id": session.session_id,
                "video_id": session.video_id,
                "platform": session.platform,
                "messages": [],
                "error": "chat_stream_failed",
            }
            self._fanout(session, "chat", err)
            self._fanout(
                session,
                "stats",
                {
                    "session_id": session.session_id,
                    "video_id": session.video_id,
                    "platform": session.platform,
                    "error": "chat_stream_failed",
                    **radar_from_vibe_counts(empty_vibe_counts()),
                },
            )
        finally:
            session.stop_event.set()
            pump.cancel()
            audio_task.cancel()
            for task in (pump, audio_task):
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._close_all_subs(session)
            async with self._lock:
                if self._sessions.get(session.session_id) is session:
                    self._sessions.pop(session.session_id, None)


_registry: SessionRegistry | None = None


def get_session_registry() -> SessionRegistry:
    global _registry
    if _registry is None:
        _registry = SessionRegistry()
    return _registry


async def iter_session_events(
    session_id: str,
    channel: Channel,
) -> AsyncIterator[dict[str, Any]]:
    """Yield payloads for an SSE subscriber until session ends or client cancels."""
    registry = get_session_registry()
    q = registry.subscribe(session_id, channel)
    if q is None:
        return
    try:
        while True:
            item = await q.get()
            if item is None:
                break
            yield item
    finally:
        registry.unsubscribe(session_id, channel, q)
