"""Top live streams by country."""

from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api", tags=["lives"])


@router.get("/lives")
async def list_top_lives(region_code: str = Query(..., min_length=2, max_length=2)) -> dict:
    """Top live streams for a country (`regionCode`). Stub until youtube_service is wired."""
    return {
        "region_code": region_code.upper(),
        "streams": [],
        "detail": "Not implemented — see youtube_service.get_top_lives_by_country",
    }
