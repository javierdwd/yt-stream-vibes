"""Active stream connect + SSE chat batches via LiveSourceAdapter + JEV."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typesafe_sdk import AsyncTypeSafeClient

from src.adapters import get_live_adapter
from src.services.jev_classifier import classify_batch

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/streams", tags=["streams"])

# Pending micro-batches waiting on JEV. Drop oldest when full so live stays fresh.
_CLASSIFY_QUEUE_SIZE = 8


@router.post("/{video_id}/connect")
async def connect_stream(video_id: str) -> dict:
    """Acknowledge stream selection. Chat ingest starts when SSE `/events` is opened."""
    adapter = get_live_adapter()
    return {
        "video_id": video_id,
        "platform": adapter.platform,
        "status": "accepted",
    }


def _enrich_messages(
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
                "spam": intent == "spam",
                "spam_reason": "jev" if intent == "spam" else None,
            }
        )
    return enriched


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _chat_event_source(video_id: str) -> AsyncIterator[str]:
    """SSE: chat micro-batches + JEV.

    Chat ingest is pumped on a separate task so pytchat keeps draining while JEV
    classifies the previous batch. Empty heartbeats are not forwarded.
    """
    adapter = get_live_adapter()
    pending: asyncio.Queue[list[dict[str, Any]] | None] = asyncio.Queue(
        maxsize=_CLASSIFY_QUEUE_SIZE
    )

    async def pump_chat() -> None:
        try:
            async for batch in adapter.stream_chat_batches(
                video_id, flush_interval_s=3.0
            ):
                if not batch:
                    continue
                if pending.full():
                    try:
                        dropped = pending.get_nowait()
                        logger.warning(
                            "Dropped stale chat batch (%d msgs) awaiting JEV for %s",
                            len(dropped or []),
                            video_id,
                        )
                    except asyncio.QueueEmpty:
                        pass
                await pending.put(batch)
        except Exception:
            logger.exception("Chat pump failed for %s", video_id)
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
                    logger.warning("Could not enqueue chat pump sentinel for %s", video_id)

    pump = asyncio.create_task(pump_chat(), name=f"chat-pump-{video_id}")
    try:
        async with AsyncTypeSafeClient() as client:
            while True:
                batch = await pending.get()
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
                    logger.exception("JEV classify failed for %s", video_id)
                    metrics = {**metrics, "error": "classify_failed"}
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.info(
                    "JEV batch video=%s msgs=%d elapsed_ms=%.0f queue=%d",
                    video_id,
                    len(batch),
                    elapsed_ms,
                    pending.qsize(),
                )

                payload: dict[str, Any] = {
                    "video_id": video_id,
                    "platform": adapter.platform,
                    "messages": _enrich_messages(
                        batch, metrics.get("classifications") or []
                    ),
                    "hype_score": metrics.get("hype_score", 0),
                    "sentiment": metrics.get("sentiment"),
                    "questions": metrics.get("questions") or [],
                }
                if metrics.get("error"):
                    payload["classify_error"] = metrics["error"]
                yield _sse(payload)
    except Exception:
        logger.exception("SSE chat stream ended with error for %s", video_id)
        yield _sse(
            {
                "video_id": video_id,
                "platform": adapter.platform,
                "messages": [],
                "error": "chat_stream_failed",
            }
        )
    finally:
        pump.cancel()
        try:
            await pump
        except asyncio.CancelledError:
            pass


@router.get("/{video_id}/events")
async def stream_events(video_id: str) -> StreamingResponse:
    """Server-Sent Events: live chat batches + JEV labels for the active stream."""
    return StreamingResponse(
        _chat_event_source(video_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
