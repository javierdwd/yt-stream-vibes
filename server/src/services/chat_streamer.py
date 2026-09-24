"""Live chat ingest via pytchat (InnerTube) — yields micro-batches."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import AsyncIterator
from typing import Any

import pytchat

logger = logging.getLogger(__name__)


def _serialize_message(item: Any) -> dict[str, Any]:
    author = getattr(item, "author", None)
    return {
        "id": str(getattr(item, "id", "") or ""),
        "author": str(getattr(author, "name", None) or ""),
        "message": str(getattr(item, "message", None) or ""),
        "timestamp": str(getattr(item, "datetime", None) or ""),
        "type": str(getattr(item, "type", None) or "textMessage"),
    }


def _poll_sync(
    video_id: str,
    queue: asyncio.Queue[list[dict[str, Any]] | None],
    loop: asyncio.AbstractEventLoop,
    stop: threading.Event,
    *,
    max_batch_size: int,
    flush_interval_s: float,
) -> None:
    """Blocking pytchat worker (LiveChatAsync is broken on current httpx)."""
    chat = None
    batch: list[dict[str, Any]] = []
    deadline = time.monotonic() + flush_interval_s

    def put(item: list[dict[str, Any]] | None) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, item)

    try:
        chat = pytchat.create(video_id=video_id, interruptable=False)
        while chat.is_alive() and not stop.is_set():
            data = chat.get()
            items = list(getattr(data, "items", None) or [])
            for raw in items:
                msg = _serialize_message(raw)
                if not msg["message"] and not msg["author"]:
                    continue
                batch.append(msg)

            now = time.monotonic()
            if batch and (len(batch) >= max_batch_size or now >= deadline):
                put(batch)
                batch = []
                deadline = now + flush_interval_s
            elif now >= deadline:
                # No empty heartbeats — avoids SSE noise / UI metric resets.
                deadline = now + flush_interval_s

            time.sleep(0.2)
    except Exception:
        logger.exception("chat_streamer worker failed for %s", video_id)
    finally:
        if batch:
            put(batch)
        if chat is not None:
            try:
                chat.terminate()
            except Exception:
                logger.debug("chat terminate failed", exc_info=True)
        put(None)


async def stream_chat_batches(
    video_id: str,
    *,
    max_batch_size: int = 20,
    flush_interval_s: float = 3.0,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Yield chat message micro-batches for `video_id`.

    Flush when `max_batch_size` is reached or every `flush_interval_s` seconds.
    Runs pytchat on a background thread so the FastAPI event loop stays free.
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[list[dict[str, Any]] | None] = asyncio.Queue()
    stop = threading.Event()
    thread = threading.Thread(
        target=_poll_sync,
        args=(video_id, queue, loop, stop),
        kwargs={
            "max_batch_size": max_batch_size,
            "flush_interval_s": flush_interval_s,
        },
        name=f"pytchat-{video_id}",
        daemon=True,
    )
    thread.start()
    try:
        while True:
            batch = await queue.get()
            if batch is None:
                break
            yield batch
    finally:
        stop.set()
