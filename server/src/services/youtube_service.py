"""YouTube Data API v3: resolve video metadata + live discovery."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime
from typing import Any

import httpx

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
DEFAULT_LIMIT = 24
_LIVES_CACHE_TTL_S = 300.0

# Major LatAm markets. search.list needs a `q`; regionCode alone returns [].
# One query per region; merge + rank by concurrent viewers.
_AMERICAS_REGIONS: tuple[tuple[str, str, str | None], ...] = (
    ("MX", "en vivo", "es"),
    ("BR", "ao vivo", "pt"),
    ("AR", "en vivo", "es"),
    ("CO", "en vivo", "es"),
)

# Always sample chat for these (even if low viewers) and include if live.
_FORCE_INCLUDE_VIDEO_IDS: tuple[str, ...] = ("6i5YJY44Rws",)

# Re-rank this many viewer-leaders by live-chat participation proxy.
_CHAT_ENGAGEMENT_TOP_N = 8
# liveChatMessages.list min maxResults is 200 (5 quota units each).
_CHAT_SAMPLE_MAX_RESULTS = 200

# In-memory top-lives cache (process-local). search.list is expensive (~100
# quota units per call × regions). TTL 5m for demos / quota headroom.
_lives_cache: list[dict[str, Any]] | None = None
_lives_cache_at: float = 0.0
_lives_cache_lock = asyncio.Lock()


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


def _has_active_live_chat(video: dict[str, Any]) -> bool:
    chat_id = (video.get("liveStreamingDetails") or {}).get("activeLiveChatId")
    return bool(chat_id and str(chat_id).strip())


def _active_live_chat_id(video: dict[str, Any]) -> str | None:
    chat_id = (video.get("liveStreamingDetails") or {}).get("activeLiveChatId")
    if not chat_id:
        return None
    text = str(chat_id).strip()
    return text or None


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


def _normalize_channel_id(raw: str | None) -> str | None:
    cid = (raw or "").strip()
    # YouTube channel ids are UC… (24 chars typical); reject handles / empty.
    if cid.startswith("UC") and len(cid) >= 20:
        return cid
    return None


def _channel_id_via_ytdlp_sync(video_id: str) -> str | None:
    """Resolve channel id via yt-dlp InnerTube metadata (no Data API quota)."""
    try:
        import yt_dlp
    except ImportError:
        return None

    url = f"https://www.youtube.com/watch?v={video_id}"
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    browser = (os.getenv("YTDLP_COOKIES_FROM_BROWSER") or "").strip()
    cookies = (os.getenv("YTDLP_COOKIES") or "").strip()
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    elif cookies:
        from src.services.audio_streamer import writable_cookie_file

        writable = writable_cookie_file(cookies)
        if writable:
            opts["cookiefile"] = writable
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None
    if not isinstance(info, dict):
        return None
    return _normalize_channel_id(info.get("channel_id"))


async def fetch_video_channel_id(video_id: str) -> str | None:
    """Return snippet.channelId via Data API (1 videos.list quota unit)."""
    vid = (video_id or "").strip()
    if not vid:
        return None
    try:
        key = _api_key()
    except YouTubeConfigError:
        return None

    async with httpx.AsyncClient(base_url=YOUTUBE_API_BASE, timeout=20.0) as client:
        try:
            res = await client.get(
                "/videos",
                params={"part": "snippet", "id": vid, "key": key},
            )
            res.raise_for_status()
        except httpx.HTTPError:
            return None

    items = res.json().get("items") or []
    if not items:
        return None
    snippet = items[0].get("snippet") or {}
    return _normalize_channel_id(snippet.get("channelId"))


async def resolve_video_channel_id(video_id: str) -> tuple[str | None, str]:
    """Resolve channel id for pytchat: Data API → yt-dlp → (None, scrape).

    Prefer API first: yt-dlp often hits YouTube bot checks without cookies.
    Returns (channel_id | None, source) where source is api|ytdlp|none.
    """
    vid = (video_id or "").strip()
    if not vid:
        return None, "none"

    cid = await fetch_video_channel_id(vid)
    if cid:
        return cid, "api"

    cid = await asyncio.to_thread(_channel_id_via_ytdlp_sync, vid)
    if cid:
        return cid, "ytdlp"

    return None, "none"


def _video_ids_from_search(payload: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for item in payload.get("items") or []:
        vid = item.get("id")
        if isinstance(vid, dict) and vid.get("videoId"):
            ids.append(vid["videoId"])
    return ids


async def _search_region_live_ids(
    client: httpx.AsyncClient,
    *,
    key: str,
    region_code: str,
    q: str,
    relevance_language: str | None,
    max_results: int,
) -> list[str]:
    params: dict[str, Any] = {
        "part": "snippet",
        "eventType": "live",
        "type": "video",
        "order": "viewCount",
        "maxResults": min(max_results, 50),
        "regionCode": region_code,
        "q": q,
        "key": key,
    }
    if relevance_language:
        params["relevanceLanguage"] = relevance_language

    try:
        search_res = await client.get("/search", params=params)
        search_res.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300]
        raise YouTubeAPIError(
            f"YouTube search.list failed ({region_code}): {detail}",
            status_code=502,
        ) from exc
    except httpx.HTTPError as exc:
        raise YouTubeAPIError(
            f"YouTube search.list unreachable ({region_code}): {exc}"
        ) from exc

    return _video_ids_from_search(search_res.json())


def _parse_iso_ts(value: str | None) -> float | None:
    if not value:
        return None
    try:
        # 2024-01-01T12:00:00Z or with fractional seconds
        text = value.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def _engagement_from_chat_payload(payload: dict[str, Any]) -> tuple[int, float, int]:
    """Return (unique_authors, msgs_per_min, message_count) from a chat sample."""
    items = payload.get("items") or []
    authors: set[str] = set()
    times: list[float] = []
    for item in items:
        author = (item.get("authorDetails") or {}).get("channelId")
        if author:
            authors.add(str(author))
        published = _parse_iso_ts((item.get("snippet") or {}).get("publishedAt"))
        if published is not None:
            times.append(published)

    msg_count = len(items)
    unique = len(authors)
    if len(times) >= 2:
        span_s = max(times) - min(times)
        msgs_per_min = (msg_count / span_s) * 60.0 if span_s > 1.0 else float(msg_count)
    else:
        msgs_per_min = float(msg_count)
    return unique, msgs_per_min, msg_count


async def _sample_chat_engagement(
    client: httpx.AsyncClient,
    *,
    key: str,
    live_chat_id: str,
) -> tuple[int, float, int]:
    try:
        res = await client.get(
            "/liveChat/messages",
            params={
                "part": "snippet,authorDetails",
                "liveChatId": live_chat_id,
                "maxResults": _CHAT_SAMPLE_MAX_RESULTS,
                "key": key,
            },
        )
        res.raise_for_status()
    except httpx.HTTPError:
        return 0, 0.0, 0
    return _engagement_from_chat_payload(res.json())


async def _rerank_by_chat_engagement(
    client: httpx.AsyncClient,
    *,
    key: str,
    streams: list[dict[str, Any]],
    chat_ids: dict[str, str],
    top_n: int = _CHAT_ENGAGEMENT_TOP_N,
) -> list[dict[str, Any]]:
    """Re-order the viewer leaders by live-chat participation proxy."""
    if not streams or top_n <= 0:
        return streams

    sample_ids: list[str] = []
    seen: set[str] = set()
    for stream in streams[:top_n]:
        sid = str(stream.get("stream_id") or "")
        if sid and sid not in seen and sid in chat_ids:
            seen.add(sid)
            sample_ids.append(sid)
    for forced_id in _FORCE_INCLUDE_VIDEO_IDS:
        if forced_id in chat_ids and forced_id not in seen:
            # Only sample if it made the live list.
            if any(s.get("stream_id") == forced_id for s in streams):
                seen.add(forced_id)
                sample_ids.append(forced_id)

    if not sample_ids:
        return streams

    scores = await asyncio.gather(
        *[
            _sample_chat_engagement(client, key=key, live_chat_id=chat_ids[sid])
            for sid in sample_ids
        ]
    )
    score_by_id = {
        sid: (unique, rate, count)
        for sid, (unique, rate, count) in zip(sample_ids, scores, strict=True)
    }

    sampled: list[dict[str, Any]] = []
    rest: list[dict[str, Any]] = []
    sampled_set = set(sample_ids)
    for stream in streams:
        sid = str(stream.get("stream_id") or "")
        if sid in sampled_set:
            sampled.append(stream)
        else:
            rest.append(stream)

    sampled.sort(
        key=lambda s: (
            score_by_id.get(str(s.get("stream_id")), (0, 0.0, 0))[0],
            score_by_id.get(str(s.get("stream_id")), (0, 0.0, 0))[1],
            s.get("concurrent_viewers") or 0,
        ),
        reverse=True,
    )
    return sampled + rest


async def _fetch_top_live_streams(*, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Hit YouTube Data API for top LatAm lives (no cache)."""
    cap = max(1, min(limit, DEFAULT_LIMIT))
    key = _api_key()
    per_region = DEFAULT_LIMIT

    async with httpx.AsyncClient(base_url=YOUTUBE_API_BASE, timeout=20.0) as client:
        region_results = await asyncio.gather(
            *[
                _search_region_live_ids(
                    client,
                    key=key,
                    region_code=region,
                    q=query,
                    relevance_language=lang,
                    max_results=per_region,
                )
                for region, query, lang in _AMERICAS_REGIONS
            ]
        )

        seen: set[str] = set()
        video_ids: list[str] = []
        for ids in region_results:
            for video_id in ids:
                if video_id in seen:
                    continue
                seen.add(video_id)
                video_ids.append(video_id)

        for forced_id in _FORCE_INCLUDE_VIDEO_IDS:
            if forced_id not in seen:
                seen.add(forced_id)
                video_ids.append(forced_id)

        if not video_ids:
            return []

        by_id: dict[str, dict[str, Any]] = {}
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i : i + 50]
            try:
                videos_res = await client.get(
                    "/videos",
                    params={
                        "part": "snippet,liveStreamingDetails,statistics",
                        "id": ",".join(chunk),
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
                raise YouTubeAPIError(
                    f"YouTube videos.list unreachable: {exc}"
                ) from exc

            for video in videos_res.json().get("items") or []:
                vid = video.get("id")
                if vid:
                    by_id[vid] = video

        streams: list[dict[str, Any]] = []
        chat_ids: dict[str, str] = {}
        for video_id, video in by_id.items():
            if (video.get("snippet") or {}).get("liveBroadcastContent") != "live":
                continue
            if not _has_active_live_chat(video):
                continue
            streams.append(_to_stream(video_id, video))
            chat_id = _active_live_chat_id(video)
            if chat_id:
                chat_ids[video_id] = chat_id

        streams.sort(
            key=lambda s: (
                s.get("concurrent_viewers") is not None,
                s.get("concurrent_viewers") or 0,
            ),
            reverse=True,
        )
        streams = await _rerank_by_chat_engagement(
            client,
            key=key,
            streams=streams,
            chat_ids=chat_ids,
        )
        return streams[:cap]


async def list_top_live_streams(*, limit: int = DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Top LatAm lives, biased to chatty streams among viewer leaders (cached ~5m)."""
    global _lives_cache, _lives_cache_at

    cap = max(1, min(limit, DEFAULT_LIMIT))
    now = time.monotonic()
    cached = _lives_cache
    if cached is not None and (now - _lives_cache_at) < _LIVES_CACHE_TTL_S:
        return cached[:cap]

    async with _lives_cache_lock:
        now = time.monotonic()
        cached = _lives_cache
        if cached is not None and (now - _lives_cache_at) < _LIVES_CACHE_TTL_S:
            return cached[:cap]

        streams = await _fetch_top_live_streams(limit=DEFAULT_LIMIT)
        _lives_cache = streams
        _lives_cache_at = time.monotonic()
        return streams[:cap]


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

        video_ids = _video_ids_from_search(search_res.json())
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
