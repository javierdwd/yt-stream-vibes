"""JEV wrapper: chat micro-batch in → structured metrics JSON out."""

from __future__ import annotations

from typing import Any, Literal

Intent = Literal["question", "hype/reaction", "technical_issue", "spam"]
Sentiment = Literal["positive", "neutral", "negative"]


async def classify_batch(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify a micro-batch with JEV.

    Expected output shape (per message / aggregate — finalize when wiring JEV):
    - intent: question | hype/reaction | technical_issue | spam
    - sentiment: positive | neutral | negative
    - hype_score: 0–100
    """
    raise NotImplementedError("Wire JEV inference here")
