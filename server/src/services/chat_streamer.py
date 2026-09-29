"""Live chat ingest via pytchat (InnerTube) — yields micro-batches."""

from __future__ import annotations

import asyncio
import errno
import logging
import threading
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytchat

logger = logging.getLogger(__name__)

_MIN_BACKOFF_S = 2.0
_MAX_BACKOFF_S = 30.0


def _is_transient_net_error(exc: BaseException) -> bool:
    """macOS EAGAIN / httpx brief read failures while polling live chat."""
    if isinstance(exc, (httpx.ReadError, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, OSError) and exc.errno in {
        errno.EAGAIN,
        errno.EWOULDBLOCK,
        errno.ECONNRESET,
        errno.ETIMEDOUT,
    }:
        return True
    cause = getattr(exc, "__cause__", None)
    if cause is not None and cause is not exc:
        return _is_transient_net_error(cause)
    return False


def _serialize_message(item: Any) -> dict[str, Any]:
    author = getattr(item, "author", None)
    return {
        "id": str(getattr(item, "id", "") or ""),
        "author": str(getattr(author, "name", None) or ""),
        "message": str(getattr(item, "message", None) or ""),
        "timestamp": str(getattr(item, "datetime", None) or ""),
        "type": str(getattr(item, "type", None) or "textMessage"),
    }


def _pytchat_death_reason(chat: Any) -> str:
    try:
        chat.raise_for_status()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    return "unknown (is_alive=False)"


def _poll_sync(
    video_id: str,
    queue: asyncio.Queue[list[dict[str, Any]] | None],
    loop: asyncio.AbstractEventLoop,
    stop: threading.Event,
    *,
    max_batch_size: int,
    flush_interval_s: float,
) -> None:
    """Blocking pytchat worker (LiveChatAsync is broken on current httpx).

    pytchat often dies on empty polls (`NoContents`). Recreate with backoff
    until `stop` — do not end the async consumer on a transient empty fetch.
    """
    chat = None
    batch: list[dict[str, Any]] = []
    deadline = time.monotonic() + flush_interval_s
    backoff_s = _MIN_BACKOFF_S

    def put(item: list[dict[str, Any]] | None) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, item)

    try:
        while not stop.is_set():
            chat = None
            got_messages = False
            try:
                chat = pytchat.create(video_id=video_id, interruptable=False)
                if not chat.is_alive():
                    reason = _pytchat_death_reason(chat)
                    logger.warning(
                        "pytchat not alive at start video=%s reason=%s",
                        video_id,
                        reason,
                    )
                else:
                    logger.info(
                        "pytchat connected video=%s replay=%s",
                        video_id,
                        bool(chat.is_replay()),
                    )

                while chat.is_alive() and not stop.is_set():
                    data = chat.get()
                    items = list(getattr(data, "items", None) or [])
                    for raw in items:
                        msg = _serialize_message(raw)
                        if not msg["message"] and not msg["author"]:
                            continue
                        batch.append(msg)
                        got_messages = True

                    now = time.monotonic()
                    if batch and (
                        len(batch) >= max_batch_size or now >= deadline
                    ):
                        put(batch)
                        batch = []
                        deadline = now + flush_interval_s
                        backoff_s = _MIN_BACKOFF_S
                    elif now >= deadline:
                        deadline = now + flush_interval_s

                    time.sleep(0.1)

                if not stop.is_set():
                    reason = _pytchat_death_reason(chat) if chat else "no chat"
                    logger.warning(
                        "pytchat died video=%s reason=%s got_messages=%s; "
                        "reconnecting in %.1fs",
                        video_id,
                        reason,
                        got_messages,
                        backoff_s,
                    )
            except Exception as exc:
                if _is_transient_net_error(exc):
                    logger.warning(
                        "pytchat transient net error video=%s err=%s; "
                        "reconnecting in %.1fs",
                        video_id,
                        exc,
                        backoff_s,
                    )
                else:
                    logger.exception(
                        "chat_streamer worker failed for %s; reconnecting in %.1fs",
                        video_id,
                        backoff_s,
                    )
            finally:
                if chat is not None:
                    try:
                        chat.terminate()
                    except Exception:
                        logger.debug("chat terminate failed", exc_info=True)
                    chat = None

            if stop.is_set():
                break
            time.sleep(backoff_s)
            backoff_s = min(backoff_s * 1.5, _MAX_BACKOFF_S)
    finally:
        if batch:
            put(batch)
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
