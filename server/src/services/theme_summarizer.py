"""OpenAI one-liner: what streamer + chat are talking about right now."""

from __future__ import annotations

import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _get_client() -> AsyncOpenAI | None:
    global _client
    key = _env("OPENAI_API_KEY")
    if not key:
        return None
    if _client is None:
        _client = AsyncOpenAI(api_key=key)
    return _client


async def summarize_theme(
    *,
    streamer_speech: str,
    chat_lines: list[str],
) -> str | None:
    """Return a short theme line, or None if skipped / failed."""
    client = _get_client()
    if client is None:
        return None

    speech = (streamer_speech or "").strip()
    lines = [ln.strip() for ln in chat_lines if (ln or "").strip()]
    if not speech and not lines:
        return None

    chat_blob = "\n".join(lines[-25:])
    if len(speech) > 2000:
        speech = speech[-2000:]
    if len(chat_blob) > 2500:
        chat_blob = chat_blob[-2500:]

    model = _env("OPENAI_MODEL", "gpt-4o-mini")
    system = (
        "You summarize live stream context for an ops dashboard. "
        "Reply with ONE short line (max ~12 words) naming the shared topic "
        "or moment that streamer speech and chat refer to. "
        "Trolling/jokes about the same topic still count as that topic. "
        "If they diverge, say the main split briefly (e.g. 'Streamer on X; chat on Y'). "
        "No quotes, no emojis, no preamble — just the line. "
        "Match the dominant language of the inputs."
    )
    user = (
        f"STREAMER SPEECH:\n{speech or '(silent)'}\n\n"
        f"RECENT CHAT:\n{chat_blob or '(empty)'}"
    )

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=48,
            temperature=0.3,
        )
    except Exception:
        logger.exception("OpenAI theme summarize failed")
        return None

    choice = resp.choices[0] if resp.choices else None
    text = (choice.message.content if choice and choice.message else None) or ""
    line = " ".join(text.strip().split())
    if not line:
        return None
    # Hard cap for UI.
    if len(line) > 120:
        line = line[:117].rstrip() + "…"
    return line
