"""Pre-normalize chat + OpenAI canonical topics for the word cloud."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

# Contiguous laugh tokens: digraph units repeated ≥2 times.
_ES_LAUGH = re.compile(
    r"(?i)(?:ja|aj|ks|sk|xd){2,}",
)
_EN_LAUGH = re.compile(
    r"(?i)(?:ha|ah){2,}",
)
_ELONGATION = re.compile(r"(.)\1{2,}")

# Canonical labels that may exceed the short-token limit.
_ALLOWED_LONG_LABELS = frozenset(
    {
        "risas (jaja)",
        "problemas técnicos / lag",
    }
)


class WordCloudItem(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description=(
            "Topic label grounded in the chat window: prefer a single noun/"
            "emote/motif (1 word; max 3). Never invent categories without "
            "clear supporting messages."
        ),
    )
    value: int = Field(
        ...,
        ge=1,
        le=100,
        description=(
            "Relative weight from evidence in the window (1–100). "
            "Higher only when the motif clearly recurs; omit weak topics."
        ),
    )

    @field_validator("text", mode="before")
    @classmethod
    def _normalize_text(cls, v: Any) -> str:
        return " ".join(str(v or "").strip().split())


class WordCloudResponse(BaseModel):
    word_cloud: list[WordCloudItem] = Field(
        default_factory=list,
        description=(
            "Evidence-backed unique topics only. Empty list is fine if chat "
            "has no clear recurring motifs."
        ),
    )


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


def normalize_chat_message(text: str) -> str:
    """Collapse laugh variants and truncate character elongations."""
    if not text:
        return ""
    out = _ES_LAUGH.sub("JAJAJA", text)
    out = _EN_LAUGH.sub("HAHAHA", out)
    out = _ELONGATION.sub(r"\1\1", out)
    return out


def _sanitize_items(items: list[WordCloudItem]) -> list[dict[str, Any]]:
    """Dedupe + drop oversized labels; no phrase-specific rewriting."""
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        label = item.text
        if not label:
            continue
        key = label.casefold()
        if key not in _ALLOWED_LONG_LABELS and (
            len(label.split()) > 3 or len(label) > 28
        ):
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append({"text": label, "value": int(item.value)})
    return result


async def extract_normalized_keywords(
    chat_messages: list[str],
    stt_transcript: str,
) -> list[dict[str, Any]]:
    """Return canonical word_cloud topics [{text, value}] (empty if skipped/failed)."""
    client = _get_client()
    if client is None:
        return []

    lines = [
        normalize_chat_message(ln.strip())
        for ln in chat_messages
        if (ln or "").strip()
    ]
    lines = [ln for ln in lines if ln]
    speech = (stt_transcript or "").strip()
    if not speech and not lines:
        return []

    chat_blob = "\n".join(f"- {ln}" for ln in lines[-80:])
    if len(speech) > 2000:
        speech = speech[-2000:]
    if len(chat_blob) > 6000:
        chat_blob = chat_blob[-6000:]

    model = _env("OPENAI_MODEL", "gpt-4o-mini")
    system = (
        "You extract TOPIC labels for a live-stream word cloud.\n"
        "Ground every topic in the provided chat (and speech only as weak context). "
        "If evidence is weak or absent, omit the topic — never invent filler buckets.\n"
        "Rules:\n"
        "1. Evidence first: a topic needs clear support in multiple chat lines "
        "(or one very strong repeated motif). Prefer fewer accurate topics over padding.\n"
        "2. Canonical merges only when chat clearly matches them — "
        'laughter → "Risas (JAJA)"; common emotes → KEKW/POG/LUL/F; '
        'explicit lag/buffer/audio/video breakage → "Problemas Técnicos / Lag". '
        "Do not add a canonical label just because it exists in these rules.\n"
        "3. Every topic must be semantically unique — merge synonyms/variants.\n"
        "4. Topic head only: prefer ONE noun/emote/name (max 3 words, ~24 chars). "
        "Convert questions/mini-phrases into the underlying topic; never leave "
        "interrogatives or full utterances.\n"
        "5. Weight by recurrence across the window; one-off lines stay low or omitted.\n"
        "Return 0–12 topics. Match the dominant chat language."
    )
    user = (
        f"STREAMER SPEECH (recent window, weak context only):\n"
        f"{speech or '(silent)'}\n\n"
        f"RECENT CHAT (normalized, {len(lines[-80:])} messages over ~60s, "
        f"oldest→newest — ONLY source of truth for topics/weights):\n"
        f"{chat_blob or '(empty)'}"
    )

    try:
        resp = await client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=WordCloudResponse,
            max_tokens=400,
            temperature=0.2,
        )
    except Exception:
        logger.exception("OpenAI keyword extract failed")
        return []

    choice = resp.choices[0] if resp.choices else None
    parsed = choice.message.parsed if choice and choice.message else None
    if parsed is None:
        refusal = getattr(choice.message, "refusal", None) if choice else None
        if refusal:
            logger.warning("OpenAI keyword extract refused: %s", refusal)
        return []
    return _sanitize_items(parsed.word_cloud)
