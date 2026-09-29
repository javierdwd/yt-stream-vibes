"""OpenAI one-liners: what the streamer vs chat are talking about."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

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


def _clip_line(text: str, *, max_len: int = 100) -> str | None:
    line = " ".join((text or "").strip().split())
    if not line:
        return None
    # Strip wrapping quotes the model sometimes copies from a single message.
    if (line.startswith('"') and line.endswith('"')) or (
        line.startswith("'") and line.endswith("'")
    ):
        line = line[1:-1].strip()
    if not line:
        return None
    if len(line) > max_len:
        line = line[: max_len - 1].rstrip() + "…"
    return line


def _too_similar_to_last_message(topic: str, chat_lines: list[str]) -> bool:
    """True when the topic is basically the last chat line (bad summary)."""
    if not topic or not chat_lines:
        return False
    last = (chat_lines[-1] or "").strip().lower()
    # "author: message" → compare message part when present.
    if ": " in last:
        last = last.split(": ", 1)[-1].strip()
    t = topic.strip().lower()
    if not last or not t:
        return False
    if t == last:
        return True
    if len(t) >= 8 and (t in last or last in t):
        return True
    return False


def _parse_topics(raw: str) -> tuple[str | None, str | None]:
    text = (raw or "").strip()
    if not text:
        return None, None
    # Prefer JSON object from the model.
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            data: Any = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return (
                    _clip_line(str(data.get("streamer") or data.get("streamer_topic") or "")),
                    _clip_line(str(data.get("chat") or data.get("chat_topic") or "")),
                )
    except json.JSONDecodeError:
        pass
    # Fallback: "streamer: … / chat: …"
    streamer = None
    chat = None
    m_s = re.search(r"streamer\s*:\s*(.+?)(?:\n|$)", text, re.I)
    m_c = re.search(r"chat\s*:\s*(.+?)(?:\n|$)", text, re.I)
    if m_s:
        streamer = _clip_line(m_s.group(1))
    if m_c:
        chat = _clip_line(m_c.group(1))
    if streamer or chat:
        return streamer, chat
    # Last resort: single line → treat as shared / streamer.
    return _clip_line(text), None


async def summarize_topics(
    *,
    streamer_speech: str,
    chat_lines: list[str],
) -> dict[str, str | None]:
    """Return short streamer vs chat topic lines (None if skipped / failed)."""
    client = _get_client()
    if client is None:
        return {"streamer_topic": None, "chat_topic": None}

    speech = (streamer_speech or "").strip()
    lines = [ln.strip() for ln in chat_lines if (ln or "").strip()]
    if not speech and not lines:
        return {"streamer_topic": None, "chat_topic": None}

    chat_blob = "\n".join(f"- {ln}" for ln in lines[-40:])
    if len(speech) > 2000:
        speech = speech[-2000:]
    if len(chat_blob) > 3500:
        chat_blob = chat_blob[-3500:]

    model = _env("OPENAI_MODEL", "gpt-4o-mini")
    system = (
        "You summarize live stream context for an ops dashboard. "
        "Reply with ONLY a JSON object: "
        '{"streamer":"...","chat":"..."}. '
        "Each value is ONE short theme phrase (max ~10 words).\n"
        "streamer: what the streamer is talking about across their recent speech "
        "(not a transcript quote).\n"
        "chat: the PREVAILING topic across the WHOLE recent chat list — "
        "look for repeated motifs, chants, and shared referents. "
        "Do NOT copy or lightly rephrase the last message alone. "
        "If chat is mixed, name the dominant cluster; ignore one-off outliers.\n"
        "Never use quotation marks around a single chat line as the topic. "
        "If a side is silent/empty, use an empty string. "
        "No markdown, no preamble. Match the dominant language of each side."
    )
    user = (
        f"STREAMER SPEECH (recent window):\n{speech or '(silent)'}\n\n"
        f"RECENT CHAT ({len(lines[-40:])} messages, oldest→newest — "
        f"summarize the set, not the last line):\n"
        f"{chat_blob or '(empty)'}"
    )

    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=80,
            temperature=0.3,
        )
    except Exception:
        logger.exception("OpenAI topic summarize failed")
        return {"streamer_topic": None, "chat_topic": None}

    choice = resp.choices[0] if resp.choices else None
    raw = (choice.message.content if choice and choice.message else None) or ""
    streamer_topic, chat_topic = _parse_topics(raw)
    # Reject chat topics that are just the latest message restated.
    if chat_topic and _too_similar_to_last_message(chat_topic, lines):
        logger.info(
            "chat_topic looked like last message (%r); keeping previous aggregate hint",
            chat_topic,
        )
        chat_topic = None
    return {"streamer_topic": streamer_topic, "chat_topic": chat_topic}


async def summarize_theme(
    *,
    streamer_speech: str,
    chat_lines: list[str],
) -> str | None:
    """Backward-compatible single line (streamer · chat). Prefer summarize_topics."""
    topics = await summarize_topics(
        streamer_speech=streamer_speech,
        chat_lines=chat_lines,
    )
    parts = [p for p in (topics.get("streamer_topic"), topics.get("chat_topic")) if p]
    if not parts:
        return None
    return " · ".join(parts)
