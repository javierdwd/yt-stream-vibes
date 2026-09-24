"""Session-scoped chat + stats SSE and teardown."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response, StreamingResponse

from src.services.session_registry import (
    Channel,
    get_session_registry,
    iter_session_events,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _event_source(session_id: str, channel: Channel) -> AsyncIterator[str]:
    registry = get_session_registry()
    if registry.get(session_id) is None:
        yield _sse({"session_id": session_id, "error": "session_not_found"})
        return

    try:
        async for payload in iter_session_events(session_id, channel):
            yield _sse(payload)
    except Exception:
        logger.exception("SSE %s failed for session %s", channel, session_id)
        yield _sse(
            {
                "session_id": session_id,
                "error": "stream_failed",
            }
        )


@router.get("/{session_id}/chat/events")
async def session_chat_events(session_id: str) -> StreamingResponse:
    """SSE: enriched chat message batches for an analysis session."""
    return StreamingResponse(
        _event_source(session_id, "chat"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{session_id}/stats/events")
async def session_stats_events(session_id: str) -> StreamingResponse:
    """SSE: rolling vibe radar + hype/sentiment/questions/spam_rate."""
    return StreamingResponse(
        _event_source(session_id, "stats"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str) -> Response:
    """Stop worker and tear down session. Idempotent if already gone."""
    await get_session_registry().stop(session_id)
    return Response(status_code=204)
