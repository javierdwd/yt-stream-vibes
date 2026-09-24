"""Active stream connect + SSE chat batches via LiveSourceAdapter."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.adapters import get_live_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/streams", tags=["streams"])


@router.post("/{video_id}/connect")
async def connect_stream(video_id: str) -> dict:
    """Acknowledge stream selection. Chat ingest starts when SSE `/events` is opened."""
    adapter = get_live_adapter()
    return {
        "video_id": video_id,
        "platform": adapter.platform,
        "status": "accepted",
    }


async def _chat_event_source(video_id: str) -> AsyncIterator[str]:
    """SSE: chat micro-batches (~3s) from the active platform adapter."""
    adapter = get_live_adapter()
    try:
        async for batch in adapter.stream_chat_batches(video_id, flush_interval_s=3.0):
            payload = {
                "video_id": video_id,
                "platform": adapter.platform,
                "messages": batch,
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    except Exception:
        logger.exception("SSE chat stream ended with error for %s", video_id)
        err = {
            "video_id": video_id,
            "platform": adapter.platform,
            "messages": [],
            "error": "chat_stream_failed",
        }
        yield f"data: {json.dumps(err)}\n\n"


@router.get("/{video_id}/events")
async def stream_events(video_id: str) -> StreamingResponse:
    """Server-Sent Events: live chat batches for the active stream."""
    return StreamingResponse(
        _chat_event_source(video_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
