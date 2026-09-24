"""Resolve the active live-source adapter.

MVP: YouTube only. Twitch will register here later — routes must not import
platform SDKs directly.
"""

from __future__ import annotations

from src.adapters.protocol import LiveSourceAdapter
from src.adapters.youtube import YouTubeAdapter

_DEFAULT = "youtube"


def get_live_adapter(platform: str = _DEFAULT) -> LiveSourceAdapter:
    key = (platform or _DEFAULT).strip().lower()
    if key == "youtube":
        return YouTubeAdapter()
    raise ValueError(f"Unsupported live platform: {platform!r}")
