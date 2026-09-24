"""Twitch Helix API: app token + resolve channel/stream metadata."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

HELIX_BASE = "https://api.twitch.tv/helix"
OAUTH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"

_app_token: str | None = None
_app_token_expires_at: float = 0.0


class TwitchConfigError(Exception):
    """Missing or invalid Twitch operator credentials."""


class TwitchAPIError(Exception):
    """Upstream Twitch Helix failure."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _client_id() -> str:
    value = (os.getenv("TWITCH_CLIENT_ID") or "").strip()
    if not value:
        raise TwitchConfigError("TWITCH_CLIENT_ID is not set")
    return value


def _client_secret() -> str:
    value = (os.getenv("TWITCH_CLIENT_SECRET") or "").strip()
    if not value:
        raise TwitchConfigError("TWITCH_CLIENT_SECRET is not set")
    return value


def bot_user_id() -> str:
    value = (os.getenv("TWITCH_BOT_USER_ID") or "").strip()
    if not value:
        raise TwitchConfigError("TWITCH_BOT_USER_ID is not set")
    return value


def bot_user_token() -> str:
    value = (os.getenv("TWITCH_BOT_TOKEN") or "").strip()
    if not value:
        raise TwitchConfigError("TWITCH_BOT_TOKEN is not set")
    return value


async def _app_access_token() -> str:
    global _app_token, _app_token_expires_at
    now = time.monotonic()
    if _app_token and now < _app_token_expires_at - 60:
        return _app_token

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            res = await client.post(
                OAUTH_TOKEN_URL,
                data={
                    "client_id": _client_id(),
                    "client_secret": _client_secret(),
                    "grant_type": "client_credentials",
                },
            )
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TwitchAPIError(
                f"Twitch app token failed: {exc.response.text[:300]}",
                status_code=503,
            ) from exc
        except httpx.HTTPError as exc:
            raise TwitchAPIError(f"Twitch app token unreachable: {exc}") from exc

    data = res.json()
    token = str(data.get("access_token") or "")
    if not token:
        raise TwitchAPIError("Twitch app token response missing access_token", status_code=503)
    expires_in = int(data.get("expires_in") or 3600)
    _app_token = token
    _app_token_expires_at = time.monotonic() + expires_in
    return token


async def _helix_get(path: str, *, params: dict[str, Any]) -> dict[str, Any]:
    token = await _app_access_token()
    headers = {
        "Client-Id": _client_id(),
        "Authorization": f"Bearer {token}",
    }
    async with httpx.AsyncClient(base_url=HELIX_BASE, timeout=20.0) as client:
        try:
            res = await client.get(path, params=params, headers=headers)
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise TwitchAPIError(
                f"Twitch Helix {path} failed: {exc.response.text[:300]}",
                status_code=502,
            ) from exc
        except httpx.HTTPError as exc:
            raise TwitchAPIError(f"Twitch Helix {path} unreachable: {exc}") from exc
    return res.json()


async def resolve_stream(login: str) -> dict[str, Any]:
    """Resolve a Twitch channel login to normalized stream metadata."""
    channel = (login or "").strip().lower()
    if not channel:
        raise TwitchAPIError("channel login is required", status_code=400)

    users = await _helix_get("/users", params={"login": channel})
    user_items = users.get("data") or []
    if not user_items:
        raise TwitchAPIError(f"Twitch user not found: {channel}", status_code=404)
    user = user_items[0]
    user_id = str(user.get("id") or "")
    display = str(user.get("display_name") or channel)
    avatar = str(user.get("profile_image_url") or "")

    streams = await _helix_get("/streams", params={"user_login": channel})
    stream_items = streams.get("data") or []
    live = bool(stream_items)
    title = ""
    viewers: int | None = None
    thumbnail = avatar
    if stream_items:
        s0 = stream_items[0]
        title = str(s0.get("title") or "")
        try:
            viewers = int(s0.get("viewer_count"))
        except (TypeError, ValueError):
            viewers = None
        tmpl = str(s0.get("thumbnail_url") or "")
        if tmpl:
            thumbnail = tmpl.replace("{width}", "440").replace("{height}", "248")

    return {
        "platform": "twitch",
        "stream_id": channel,
        "video_id": channel,
        "broadcaster_id": user_id,
        "title": title or f"{display} on Twitch",
        "channel": display,
        "thumbnail_url": thumbnail,
        "concurrent_viewers": viewers,
        "live": live,
    }


async def create_eventsub_chat_subscription(
    *,
    broadcaster_id: str,
    session_id: str,
) -> dict[str, Any]:
    """Create channel.chat.message EventSub subscription over an existing WS session."""
    headers = {
        "Client-Id": _client_id(),
        "Authorization": f"Bearer {bot_user_token()}",
        "Content-Type": "application/json",
    }
    body = {
        "type": "channel.chat.message",
        "version": "1",
        "condition": {
            "broadcaster_user_id": broadcaster_id,
            "user_id": bot_user_id(),
        },
        "transport": {
            "method": "websocket",
            "session_id": session_id,
        },
    }
    async with httpx.AsyncClient(base_url=HELIX_BASE, timeout=20.0) as client:
        try:
            res = await client.post(
                "/eventsub/subscriptions",
                headers=headers,
                json=body,
            )
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:400]
            status = 503 if exc.response.status_code in {401, 403} else 502
            raise TwitchAPIError(
                f"EventSub subscribe failed: {detail}",
                status_code=status,
            ) from exc
        except httpx.HTTPError as exc:
            raise TwitchAPIError(f"EventSub subscribe unreachable: {exc}") from exc
    return res.json()
