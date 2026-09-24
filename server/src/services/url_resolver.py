"""Parse YouTube / Twitch watch URLs into platform + stream_id."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
_TWITCH_HOSTS = {"twitch.tv", "www.twitch.tv", "m.twitch.tv"}

_YOUTUBE_ID_RE = re.compile(r"^[\w-]{11}$")
_TWITCH_LOGIN_RE = re.compile(r"^[a-zA-Z0-9_]{1,25}$")
_TWITCH_RESERVED = {
    "directory",
    "videos",
    "downloads",
    "jobs",
    "p",
    "privacy",
    "settings",
    "subscriptions",
    "turbo",
    "search",
    "inventory",
    "wallet",
    "drops",
    "prime",
    "popout",
    "embed",
    "login",
    "signup",
    "logout",
}


class UrlResolveError(Exception):
    """URL could not be parsed into a supported live stream reference."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ParsedStreamUrl:
    platform: str
    stream_id: str


def parse_stream_url(raw: str) -> ParsedStreamUrl:
    text = (raw or "").strip()
    if not text:
        raise UrlResolveError("url is required")

    if "://" not in text:
        text = "https://" + text

    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host_key = host
    else:
        host_key = host

    if host_key in _YOUTUBE_HOSTS or host in _YOUTUBE_HOSTS:
        return ParsedStreamUrl(platform="youtube", stream_id=_youtube_id(parsed))
    if host_key in _TWITCH_HOSTS or host in _TWITCH_HOSTS:
        return ParsedStreamUrl(platform="twitch", stream_id=_twitch_login(parsed))

    raise UrlResolveError(f"Unsupported host: {host or 'unknown'}")


def _youtube_id(parsed) -> str:
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""

    if host in {"youtu.be", "www.youtu.be"}:
        candidate = path.strip("/").split("/")[0] if path.strip("/") else ""
    else:
        qs = parse_qs(parsed.query or "")
        if "v" in qs and qs["v"]:
            candidate = qs["v"][0]
        else:
            parts = [p for p in path.split("/") if p]
            candidate = ""
            if len(parts) >= 2 and parts[0] in {"live", "embed", "shorts", "v"}:
                candidate = parts[1]
            elif parts:
                candidate = parts[-1]

    if not _YOUTUBE_ID_RE.match(candidate or ""):
        raise UrlResolveError("Could not extract a YouTube video id from url")
    return candidate


def _twitch_login(parsed) -> str:
    parts = [p for p in (parsed.path or "").split("/") if p]
    if not parts:
        raise UrlResolveError("Could not extract a Twitch channel from url")
    if parts[0].lower() in {"videos", "clip", "clips", "collections", "events"}:
        raise UrlResolveError("Twitch VOD/clip URLs are not supported; use a channel URL")
    login = parts[0].lower()
    if login in _TWITCH_RESERVED or not _TWITCH_LOGIN_RE.match(login):
        raise UrlResolveError("Could not extract a Twitch channel from url")
    return login
