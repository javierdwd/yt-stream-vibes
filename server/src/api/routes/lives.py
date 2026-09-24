"""Search live streams via the active platform adapter."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.adapters import get_live_adapter
from src.adapters.protocol import LiveSourceError

router = APIRouter(prefix="/api", tags=["lives"])


@router.get("/lives")
async def list_lives(q: str = Query(..., min_length=1, max_length=100)) -> dict:
    """Live streams matching `q` — platform search behind LiveSourceAdapter."""
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="q is required")

    adapter = get_live_adapter()
    try:
        streams = await adapter.search_lives(query)
    except LiveSourceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return {
        "q": query,
        "platform": adapter.platform,
        "streams": streams,
    }
