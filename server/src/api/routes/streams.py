"""Stream resolve + connect (creates analysis session)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.adapters import get_live_adapter
from src.adapters.protocol import LiveSourceError
from src.services.session_registry import get_session_registry
from src.services.url_resolver import UrlResolveError, parse_stream_url

router = APIRouter(prefix="/api/streams", tags=["streams"])

Platform = Literal["youtube", "twitch"]


class ResolveBody(BaseModel):
    url: str = Field(..., min_length=1, max_length=500)


@router.post("/resolve")
async def resolve_stream_url(body: ResolveBody) -> dict:
    """Parse a YouTube/Twitch URL and return platform metadata."""
    try:
        parsed = parse_stream_url(body.url)
    except UrlResolveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    try:
        adapter = get_live_adapter(parsed.platform)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        meta = await adapter.resolve_stream(parsed.stream_id)
    except LiveSourceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return {
        "platform": parsed.platform,
        "stream_id": parsed.stream_id,
        "title": meta.get("title") or "",
        "channel": meta.get("channel") or "",
        "thumbnail_url": meta.get("thumbnail_url") or "",
        "concurrent_viewers": meta.get("concurrent_viewers"),
        "live": bool(meta.get("live")),
    }


@router.post("/{stream_id}/connect")
async def connect_stream(
    stream_id: str,
    platform: Platform = Query("youtube"),
) -> dict:
    """Start analysis session for platform + stream_id."""
    sid = stream_id.strip()
    if not sid:
        raise HTTPException(status_code=400, detail="stream_id is required")

    try:
        adapter = get_live_adapter(platform)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session = await get_session_registry().create(platform=platform, stream_id=sid)
    return {
        "session_id": session.session_id,
        "stream_id": sid,
        "video_id": sid,
        "platform": adapter.platform,
        "status": "accepted",
    }
