"""Twitch live chat via EventSub WebSocket (channel.chat.message).

Uses operator bot token (TWITCH_BOT_TOKEN) — no end-user login.
Transport matches Twitch's recommended EventSub path (same events TwitchIO 3 wraps).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from websockets.asyncio.client import connect as ws_connect

from src.services import twitch_helix

logger = logging.getLogger(__name__)

EVENTSUB_WS = "wss://eventsub.wss.twitch.tv/ws"


def _serialize_event(event: dict[str, Any]) -> dict[str, Any] | None:
    message_obj = event.get("message") or {}
    text = str(message_obj.get("text") or "").strip()
    author = str(event.get("chatter_user_name") or event.get("chatter_user_login") or "")
    msg_id = str(event.get("message_id") or "")
    if not text and not author:
        return None
    return {
        "id": msg_id,
        "author": author,
        "message": text,
        "timestamp": str(event.get("message_timestamp") or ""),
        "type": "textMessage",
    }


async def stream_chat_batches(
    channel_login: str,
    *,
    max_batch_size: int = 20,
    flush_interval_s: float = 3.0,
) -> AsyncIterator[list[dict[str, Any]]]:
    """Yield normalized chat micro-batches for a Twitch channel login."""
    meta = await twitch_helix.resolve_stream(channel_login)
    broadcaster_id = str(meta.get("broadcaster_id") or "")
    if not broadcaster_id:
        raise twitch_helix.TwitchAPIError(
            "Missing broadcaster_id for Twitch chat",
            status_code=502,
        )

    # Ensure bot credentials exist up front.
    twitch_helix.bot_user_token()
    twitch_helix.bot_user_id()

    out: asyncio.Queue[list[dict[str, Any]] | None] = asyncio.Queue(maxsize=32)
    stop = asyncio.Event()

    async def reader() -> None:
        batch: list[dict[str, Any]] = []
        deadline = time.monotonic() + flush_interval_s

        async def flush() -> None:
            nonlocal batch, deadline
            if not batch:
                deadline = time.monotonic() + flush_interval_s
                return
            try:
                out.put_nowait(batch)
            except asyncio.QueueFull:
                try:
                    out.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    out.put_nowait(batch)
                except asyncio.QueueFull:
                    pass
            batch = []
            deadline = time.monotonic() + flush_interval_s

        try:
            async with ws_connect(
                EVENTSUB_WS,
                ping_interval=20,
                ping_timeout=20,
                max_size=8 * 1024 * 1024,
            ) as ws:
                session_id: str | None = None
                while not stop.is_set():
                    timeout = max(0.05, deadline - time.monotonic())
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    except asyncio.TimeoutError:
                        await flush()
                        continue

                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("Twitch EventSub non-JSON frame")
                        continue

                    meta_msg = payload.get("metadata") or {}
                    msg_type = meta_msg.get("message_type")
                    body = payload.get("payload") or {}

                    if msg_type == "session_welcome":
                        session = body.get("session") or {}
                        session_id = str(session.get("id") or "")
                        if not session_id:
                            raise twitch_helix.TwitchAPIError(
                                "EventSub welcome missing session id",
                                status_code=502,
                            )
                        await twitch_helix.create_eventsub_chat_subscription(
                            broadcaster_id=broadcaster_id,
                            session_id=session_id,
                        )
                        logger.info(
                            "Twitch EventSub subscribed channel=%s broadcaster=%s",
                            channel_login,
                            broadcaster_id,
                        )
                        continue

                    if msg_type == "session_keepalive":
                        if time.monotonic() >= deadline:
                            await flush()
                        continue

                    if msg_type == "session_reconnect":
                        logger.warning(
                            "Twitch EventSub reconnect requested for %s", channel_login
                        )
                        break

                    if msg_type == "notification":
                        event = body.get("event") or {}
                        msg = _serialize_event(event)
                        if msg:
                            batch.append(msg)
                        if len(batch) >= max_batch_size or time.monotonic() >= deadline:
                            await flush()
                        continue

                    if msg_type == "revocation":
                        logger.error(
                            "Twitch EventSub revoked for %s: %s",
                            channel_login,
                            body,
                        )
                        break
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Twitch EventSub reader failed for %s", channel_login)
        finally:
            await flush()
            try:
                out.put_nowait(None)
            except asyncio.QueueFull:
                pass

    task = asyncio.create_task(reader(), name=f"twitch-chat-{channel_login}")
    try:
        while True:
            item = await out.get()
            if item is None:
                break
            if item:
                yield item
    finally:
        stop.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
