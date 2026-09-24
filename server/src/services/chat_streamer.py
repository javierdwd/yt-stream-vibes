"""Live chat ingest via pytchat (InnerTube) — yields micro-batches."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any


async def stream_chat_batches(
    video_id: str,
    *,
    max_batch_size: int = 20,
    flush_interval_s: float = 3.0,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Yield chat message micro-batches for `video_id`.

    Flush when `max_batch_size` is reached or every `flush_interval_s` seconds.
    Runs as a background worker; must not block the FastAPI event loop.
    """
    raise NotImplementedError("Wire pytchat micro-batching here")
    yield []  # pragma: no cover — keeps this an async generator for type checkers
