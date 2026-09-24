"""Resolve the active live-source adapter by platform."""

from __future__ import annotations

from src.adapters.protocol import LiveSourceAdapter
from src.adapters.twitch import TwitchAdapter
from src.adapters.youtube import YouTubeAdapter

_DEFAULT = "youtube"


def get_live_adapter(platform: str = _DEFAULT) -> LiveSourceAdapter:
    key = (platform or _DEFAULT).strip().lower()
    if key == "youtube":
        return YouTubeAdapter()
    if key == "twitch":
        return TwitchAdapter()
    raise ValueError(f"Unsupported live platform: {platform!r}")
