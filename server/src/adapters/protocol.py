"""Platform-agnostic live source adapter (YouTube now; Twitch later)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class LiveSourceError(Exception):
    """Upstream live-platform failure (config or API)."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class LiveSourceAdapter(Protocol):
    """Fetch lives + chat behind one interface so routes stay platform-agnostic.

    Next platform (Twitch) should implement this — do not call YouTube/Twitch
    SDKs from `api/routes`.
    """

    platform: str

    async def search_lives(self, q: str, *, limit: int = 16) -> list[dict[str, Any]]:
        """Return normalized live stream cards for search query `q`."""
        ...

    def stream_chat_batches(
        self,
        stream_id: str,
        *,
        max_batch_size: int = 20,
        flush_interval_s: float = 3.0,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Yield normalized chat micro-batches for `stream_id`."""
        ...
