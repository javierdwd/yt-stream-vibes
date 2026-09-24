"""Deprecated live search — use POST /api/streams/resolve with a stream URL."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["lives"])


@router.get("/lives")
async def list_lives_deprecated() -> JSONResponse:
    return JSONResponse(
        status_code=410,
        content={
            "detail": "Live search is deprecated. POST /api/streams/resolve with a YouTube or Twitch URL.",
        },
    )
