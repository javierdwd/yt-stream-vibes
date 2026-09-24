"""YouTube Data API v3: top live streams by country + live metrics."""

from __future__ import annotations

from typing import Any


async def get_top_lives_by_country(region_code: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Return top live streams for `region_code` ordered by view count.

    Uses search.list (eventType=live, type=video, order=viewCount) and
    videos.list (liveStreamingDetails, statistics) for concurrent viewers.
    """
    raise NotImplementedError("Wire YouTube Data API v3 here")
