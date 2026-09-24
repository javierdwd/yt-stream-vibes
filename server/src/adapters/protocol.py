"""Platform-agnostic live source adapter (YouTube + Twitch)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class LiveSourceError(Exception):
    """Upstream live-platform failure (config or API)."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class LiveSourceAdapter(Protocol):
    """Resolve stream metadata + chat behind one interface.

    Platform SDKs stay in adapters/services — never call them from api/routes.
    """

    platform: str

    async def resolve_stream(self, stream_id: str) -> dict[str, Any]:
        """Return normalized metadata for `stream_id` (video id or channel login)."""
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
