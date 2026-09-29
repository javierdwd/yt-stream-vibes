"""Live stream discovery for the home feed."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.adapters import get_live_adapter
from src.adapters.protocol import LiveSourceError

router = APIRouter(prefix="/api", tags=["lives"])


@router.get("/lives")
async def list_lives(
    limit: int = Query(24, ge=1, le=24),
    platform: str = Query("youtube"),
) -> dict:
    """Top live streams (YouTube Americas / LatAm by concurrent viewers)."""
    try:
        adapter = get_live_adapter(platform)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        streams = await adapter.list_top_lives(limit=limit)
    except LiveSourceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return {"streams": streams, "count": len(streams)}
