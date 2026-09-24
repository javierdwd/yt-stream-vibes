"""Search live streams by free-text query."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.services.youtube_service import (
    YouTubeAPIError,
    YouTubeConfigError,
    search_live_streams,
)

router = APIRouter(prefix="/api", tags=["lives"])


@router.get("/lives")
async def list_lives(q: str = Query(..., min_length=1, max_length=100)) -> dict:
    """Live streams matching `q` (channel name, topic, etc.) — YouTube-style search."""
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="q is required")

    try:
        streams = await search_live_streams(query)
    except YouTubeConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except YouTubeAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return {
        "q": query,
        "streams": streams,
    }
