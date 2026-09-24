"""Twitch implementation of LiveSourceAdapter (Helix + EventSub chat)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from src.adapters.protocol import LiveSourceError
from src.services import twitch_chat, twitch_helix


class TwitchAdapter:
    platform = "twitch"

    async def resolve_stream(self, stream_id: str) -> dict[str, Any]:
        try:
            return await twitch_helix.resolve_stream(stream_id)
        except twitch_helix.TwitchConfigError as exc:
            raise LiveSourceError(str(exc), status_code=503) from exc
        except twitch_helix.TwitchAPIError as exc:
            raise LiveSourceError(str(exc), status_code=exc.status_code) from exc

    def stream_chat_batches(
        self,
        stream_id: str,
        *,
        max_batch_size: int = 20,
        flush_interval_s: float = 3.0,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        return twitch_chat.stream_chat_batches(
            stream_id,
            max_batch_size=max_batch_size,
            flush_interval_s=flush_interval_s,
        )
