"""Active stream connect + SSE metrics."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/streams", tags=["streams"])


@router.post("/{video_id}/connect")
async def connect_stream(video_id: str) -> dict:
    """Select an active stream for chat ingest. Stub until chat_streamer is wired."""
    return {
        "video_id": video_id,
        "status": "accepted",
        "detail": "Not implemented — see chat_streamer.stream_chat_batches",
    }


async def _metrics_event_source(video_id: str) -> AsyncIterator[str]:
    """SSE heartbeat stub. Replace with JEV metrics broadcast for the active stream."""
    while True:
        payload = {
            "video_id": video_id,
            "hype_score": 0,
            "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
            "questions": [],
        }
        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(3)


@router.get("/{video_id}/events")
async def stream_events(video_id: str) -> StreamingResponse:
    """Server-Sent Events: live metrics for the active stream."""
    return StreamingResponse(
        _metrics_event_source(video_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
