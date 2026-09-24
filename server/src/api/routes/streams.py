"""Active stream connect — creates an in-memory analysis session."""

from __future__ import annotations

from fastapi import APIRouter

from src.adapters import get_live_adapter
from src.services.session_registry import get_session_registry

router = APIRouter(prefix="/api/streams", tags=["streams"])


@router.post("/{video_id}/connect")
async def connect_stream(video_id: str) -> dict:
    """Start analysis session (chat pump + JEV). SSE clients subscribe by session_id."""
    adapter = get_live_adapter()
    session = await get_session_registry().create(video_id)
    return {
        "session_id": session.session_id,
        "video_id": video_id,
        "platform": adapter.platform,
        "status": "accepted",
    }
