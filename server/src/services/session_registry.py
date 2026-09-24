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
from src.services.jev_classifier import (
    classify_batch,
    empty_vibe_counts,
    radar_from_vibe_counts,
)

logger = logging.getLogger(__name__)

_CLASSIFY_QUEUE_SIZE = 8
_SUBSCRIBER_QUEUE_SIZE = 32
_ROLLING_WINDOW_S = 30.0
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
                "sentiment": (label or {}).get("sentiment"),
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
    sentiment: str | None
    hype_score: int
    question: dict[str, Any] | None


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
    last_stats: dict[str, Any] | None = None


class SessionRegistry:
    """Process-local session map. Not multi-worker safe (MVP)."""

    def __init__(self) -> None:
        self._sessions: dict[str, AnalysisSession] = {}
        self._lock = asyncio.Lock()

    async def create(self, video_id: str) -> AnalysisSession:
        adapter = get_live_adapter()
        session_id = uuid.uuid4().hex
        session = AnalysisSession(
            session_id=session_id,
            video_id=video_id,
            platform=adapter.platform,
        )
        async with self._lock:
            self._sessions[session_id] = session
        session.worker = asyncio.create_task(
            self._run_session(session),
            name=f"session-{session_id[:8]}",
        )
        logger.info("Session started id=%s video=%s", session_id, video_id)
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

    def _prune_window(self, session: AnalysisSession, now: float) -> None:
        cutoff = now - _ROLLING_WINDOW_S
        while session.window and session.window[0].ts < cutoff:
            session.window.popleft()

    def _ingest_classifications(
        self,
        session: AnalysisSession,
        classifications: list[dict[str, Any]],
        now: float,
    ) -> None:
        for item in classifications:
            spam = item.get("intent") == "spam"
            question = None
            if not spam and item.get("intent") == "question":
                question = {
                    "id": item["id"],
                    "author": item["author"],
                    "message": item["message"],
                }
            session.window.append(
                _WindowSample(
                    ts=now,
                    vibe=None if spam else item.get("vibe"),
                    spam=spam,
                    sentiment=None if spam else (item.get("sentiment") or "neutral"),
                    hype_score=0 if spam else int(item.get("hype_score") or 0),
                    question=question,
                )
            )
        self._prune_window(session, now)

    def _stats_snapshot(self, session: AnalysisSession, now: float) -> dict[str, Any]:
        self._prune_window(session, now)
        vibe_counts = empty_vibe_counts()
        sentiment = {"positive": 0, "neutral": 0, "negative": 0}
        hype_values: list[int] = []
        questions: list[dict[str, Any]] = []
        spam_count = 0
        for sample in session.window:
            if sample.spam:
                spam_count += 1
                continue
            if sample.vibe in vibe_counts:
                vibe_counts[sample.vibe] += 1
            if sample.sentiment in sentiment:
                sentiment[sample.sentiment] += 1
            hype_values.append(sample.hype_score)
            if sample.question:
                questions.append(sample.question)

        message_count = len(session.window)
        non_spam = message_count - spam_count
        avg_hype = int(round(sum(hype_values) / len(hype_values))) if hype_values else 0
        spam_rate = (spam_count / message_count) if message_count else 0.0
        radar = radar_from_vibe_counts(vibe_counts)

        return {
            "session_id": session.session_id,
            "video_id": session.video_id,
            "platform": session.platform,
            "hype_score": avg_hype,
            "sentiment": sentiment,
            "questions": questions[-40:],
            "spam_rate": round(spam_rate, 4),
            "spam_count": spam_count,
            "window": {
                "seconds": int(_ROLLING_WINDOW_S),
                "message_count": message_count,
                "non_spam_count": non_spam,
            },
            **radar,
        }

    async def _run_session(self, session: AnalysisSession) -> None:
        adapter = get_live_adapter()
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

        pump = asyncio.create_task(
            pump_chat(), name=f"chat-pump-{session.session_id[:8]}"
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
                        "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
                        "questions": [],
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

                    stats = self._stats_snapshot(session, now)
                    if metrics.get("error"):
                        stats["classify_error"] = metrics["error"]
                    session.last_stats = stats
                    self._fanout(session, "stats", stats)
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
            pump.cancel()
            try:
                await pump
            except asyncio.CancelledError:
                pass
            session.stop_event.set()
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
