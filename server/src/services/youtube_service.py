"""YouTube Data API v3: resolve video metadata (+ legacy search helper)."""

from __future__ import annotations

import os
from typing import Any

import httpx

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
DEFAULT_LIMIT = 16


class YouTubeConfigError(Exception):
    """Missing or invalid local YouTube API configuration."""


class YouTubeAPIError(Exception):
    """Upstream YouTube Data API failure."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _api_key() -> str:
    key = (os.getenv("YOUTUBE_API_KEY") or "").strip()
    if not key:
        raise YouTubeConfigError("YOUTUBE_API_KEY is not set")
    return key


def _thumbnail_url(snippet: dict[str, Any]) -> str:
    thumbs = snippet.get("thumbnails") or {}
    for size in ("medium", "high", "default"):
        url = (thumbs.get(size) or {}).get("url")
        if url:
            return url
    return ""


def _concurrent_viewers(video: dict[str, Any]) -> int | None:
    raw = (video.get("liveStreamingDetails") or {}).get("concurrentViewers")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _to_stream(video_id: str, video: dict[str, Any]) -> dict[str, Any]:
    snippet = video.get("snippet") or {}
    live = (video.get("snippet") or {}).get("liveBroadcastContent")
    return {
        "platform": "youtube",
        "stream_id": video_id,
        "video_id": video_id,
        "title": snippet.get("title") or "",
        "channel": snippet.get("channelTitle") or "",
        "thumbnail_url": _thumbnail_url(snippet),
        "concurrent_viewers": _concurrent_viewers(video),
        "live": live == "live",
    }


async def resolve_stream(video_id: str) -> dict[str, Any]:
    """Fetch metadata for a single video id via videos.list."""
    vid = (video_id or "").strip()
    if not vid:
        raise YouTubeAPIError("video_id is required", status_code=400)

    key = _api_key()
    async with httpx.AsyncClient(base_url=YOUTUBE_API_BASE, timeout=20.0) as client:
        try:
            videos_res = await client.get(
                "/videos",
                params={
                    "part": "snippet,liveStreamingDetails,statistics",
                    "id": vid,
                    "key": key,
                },
            )
            videos_res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise YouTubeAPIError(
                f"YouTube videos.list failed: {detail}",
                status_code=502,
            ) from exc
        except httpx.HTTPError as exc:
            raise YouTubeAPIError(f"YouTube videos.list unreachable: {exc}") from exc

        items = videos_res.json().get("items") or []
        if not items:
            raise YouTubeAPIError("YouTube video not found", status_code=404)
        return _to_stream(vid, items[0])


async def search_live_streams(
    q: str,
    *,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Deprecated: kept for local debugging only."""
    query = q.strip()
    if not query:
        return []

    key = _api_key()

    async with httpx.AsyncClient(base_url=YOUTUBE_API_BASE, timeout=20.0) as client:
        try:
            search_res = await client.get(
                "/search",
                params={
                    "part": "snippet",
                    "eventType": "live",
                    "type": "video",
                    "order": "relevance",
                    "maxResults": min(limit, 50),
                    "q": query,
                    "key": key,
                },
            )
            search_res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise YouTubeAPIError(
                f"YouTube search.list failed: {detail}",
                status_code=502,
            ) from exc
        except httpx.HTTPError as exc:
            raise YouTubeAPIError(f"YouTube search.list unreachable: {exc}") from exc

        items = search_res.json().get("items") or []
        video_ids = [
            item["id"]["videoId"]
            for item in items
            if isinstance(item.get("id"), dict) and item["id"].get("videoId")
        ]
        if not video_ids:
            return []

        try:
            videos_res = await client.get(
                "/videos",
                params={
                    "part": "snippet,liveStreamingDetails,statistics",
                    "id": ",".join(video_ids),
                    "key": key,
                },
            )
            videos_res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise YouTubeAPIError(
                f"YouTube videos.list failed: {detail}",
                status_code=502,
            ) from exc
        except httpx.HTTPError as exc:
            raise YouTubeAPIError(f"YouTube videos.list unreachable: {exc}") from exc

        by_id = {v["id"]: v for v in (videos_res.json().get("items") or []) if "id" in v}
        streams: list[dict[str, Any]] = []
        for video_id in video_ids:
            video = by_id.get(video_id)
            if not video:
                continue
            streams.append(_to_stream(video_id, video))
        return streams[:limit]
