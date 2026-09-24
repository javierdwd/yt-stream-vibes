"""JEV (TypeSafe) wrapper: chat micro-batch in → structured metrics JSON out."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from typesafe_sdk import AsyncTypeSafeClient, Choice, Score

logger = logging.getLogger(__name__)

Intent = Literal["question", "hype/reaction", "technical_issue", "spam"]
Sentiment = Literal["positive", "neutral", "negative"]

_HYPE_LEVELS = (
    "No hype or energy",
    "Mild reaction",
    "Clear excitement",
    "Strong hype / cheering",
    "Peak frenzy",
)

_QUESTIONS = {
    "intent": Choice(
        instructions="What is the primary intent of this YouTube live chat message?",
        criteria={
            "question": "Asks a question or seeks information from the streamer or chat",
            "hype/reaction": "Cheering, reacting, emotes, hype — no real question",
            "technical_issue": "Reports playback, audio, lag, buffering, or stream tech problems",
            "spam": "Spam, bots, scams, irrelevant promo, or nonsense flood",
        },
    ),
    "sentiment": Choice(
        instructions="Overall sentiment of this live chat message",
        criteria={
            "positive": "Positive, supportive, happy",
            "neutral": "Neutral, mixed, or unclear",
            "negative": "Negative, angry, hostile, or disappointed",
        },
    ),
    "hype": Score(
        instructions="How much live-chat hype or energy does this message show?",
        criteria=list(_HYPE_LEVELS),
    ),
}

_MAX_CONCURRENCY = 8


def _hype_to_0_100(raw_score: float) -> int:
    """Map TypeSafe Score (0..len(levels)-1) onto 0–100."""
    top = float(len(_HYPE_LEVELS) - 1)
    if top <= 0:
        return 0
    return int(max(0, min(100, round(float(raw_score) / top * 100))))


async def _classify_one(
    client: AsyncTypeSafeClient,
    message: dict[str, Any],
    *,
    sem: asyncio.Semaphore,
) -> dict[str, Any]:
    text = (message.get("message") or "").strip()
    author = (message.get("author") or "").strip()
    msg_id = str(message.get("id") or "")

    base = {
        "id": msg_id,
        "author": author,
        "message": text,
        "intent": "spam" if not text else "hype/reaction",
        "sentiment": "neutral",
        "hype_score": 0,
    }
    if not text:
        return base

    async with sem:
        response = await client.system_one(
            state={"author": author, "message": text},
            questions=_QUESTIONS,
        )

    intent = response.choices["intent"].choice
    sentiment = response.choices["sentiment"].choice
    hype_raw = float(response.scores["hype"].score)

    return {
        **base,
        "intent": intent,
        "sentiment": sentiment,
        "hype_score": _hype_to_0_100(hype_raw),
        "intent_confidence": float(response.choices["intent"].confidence or 0),
        "sentiment_confidence": float(response.choices["sentiment"].confidence or 0),
    }


async def classify_batch(
    messages: list[dict[str, Any]],
    *,
    client: AsyncTypeSafeClient | None = None,
) -> dict[str, Any]:
    """Classify a micro-batch with JEV (TypeSafe System One).

    Spam is JEV `intent=spam` only (no heuristic session memory).
    Returns per-message labels plus batch aggregates for the analytics panel.
    """
    if not messages:
        return {
            "classifications": [],
            "hype_score": 0,
            "sentiment": {"positive": 0, "neutral": 0, "negative": 0},
            "questions": [],
        }

    owns_client = client is None
    if owns_client:
        client = AsyncTypeSafeClient()

    assert client is not None
    sem = asyncio.Semaphore(_MAX_CONCURRENCY)

    try:
        if owns_client:
            async with client:
                results = await _run_all(client, messages, sem)
        else:
            results = await _run_all(client, messages, sem)
    except Exception:
        logger.exception("JEV classify_batch failed (%d messages)", len(messages))
        raise

    classifications: list[dict[str, Any]] = []
    sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
    hype_values: list[int] = []
    questions: list[dict[str, Any]] = []

    for item in results:
        classifications.append(item)
        if item.get("intent") == "spam":
            continue
        sent = item.get("sentiment") or "neutral"
        if sent in sentiment_counts:
            sentiment_counts[sent] += 1
        hype_values.append(int(item.get("hype_score") or 0))
        if item.get("intent") == "question":
            questions.append(
                {
                    "id": item["id"],
                    "author": item["author"],
                    "message": item["message"],
                }
            )

    avg_hype = int(round(sum(hype_values) / len(hype_values))) if hype_values else 0

    return {
        "classifications": classifications,
        "hype_score": avg_hype,
        "sentiment": sentiment_counts,
        "questions": questions,
    }


async def _run_all(
    client: AsyncTypeSafeClient,
    messages: list[dict[str, Any]],
    sem: asyncio.Semaphore,
) -> list[dict[str, Any]]:
    tasks = [_classify_one(client, m, sem=sem) for m in messages]
    settled = await asyncio.gather(*tasks, return_exceptions=True)
    out: list[dict[str, Any]] = []
    for msg, result in zip(messages, settled, strict=True):
        if isinstance(result, BaseException):
            logger.warning("JEV failed for message %s: %s", msg.get("id"), result)
            out.append(
                {
                    "id": str(msg.get("id") or ""),
                    "author": str(msg.get("author") or ""),
                    "message": str(msg.get("message") or ""),
                    "intent": "hype/reaction",
                    "sentiment": "neutral",
                    "hype_score": 0,
                    "error": str(result),
                }
            )
        else:
            out.append(result)
    return out
