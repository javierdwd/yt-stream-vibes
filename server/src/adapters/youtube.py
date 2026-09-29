"""YouTube implementation of LiveSourceAdapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from src.adapters.protocol import LiveSourceError
from src.services import chat_streamer, youtube_service


class YouTubeAdapter:
    platform = "youtube"

    async def resolve_stream(self, stream_id: str) -> dict[str, Any]:
        try:
            return await youtube_service.resolve_stream(stream_id)
        except youtube_service.YouTubeConfigError as exc:
            raise LiveSourceError(str(exc), status_code=503) from exc
        except youtube_service.YouTubeAPIError as exc:
            raise LiveSourceError(str(exc), status_code=exc.status_code) from exc

    async def list_top_lives(self, *, limit: int = 24) -> list[dict[str, Any]]:
        try:
            return await youtube_service.list_top_live_streams(limit=limit)
        except youtube_service.YouTubeConfigError as exc:
            raise LiveSourceError(str(exc), status_code=503) from exc
        except youtube_service.YouTubeAPIError as exc:
            raise LiveSourceError(str(exc), status_code=exc.status_code) from exc

    def stream_chat_batches(
        self,
        stream_id: str,
        *,
        max_batch_size: int = 20,
        flush_interval_s: float = 3.0,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        return chat_streamer.stream_chat_batches(
            stream_id,
            max_batch_size=max_batch_size,
            flush_interval_s=flush_interval_s,
        )
