"""JEV (TypeSafe) wrapper: chat micro-batch in → structured metrics JSON out."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from typesafe_sdk import AsyncTypeSafeClient, Choice, Score

logger = logging.getLogger(__name__)

Intent = Literal["question", "hype/reaction", "technical_issue", "spam"]
Vibe = Literal[
    "laughter_humor",
    "hype_pog",
    "troll_sarcasm",
    "support_wholesome",
    "tension_drama",
    "curiosity_context",
]

VIBE_AXES: tuple[Vibe, ...] = (
    "laughter_humor",
    "hype_pog",
    "troll_sarcasm",
    "support_wholesome",
    "tension_drama",
    "curiosity_context",
)

RADAR_LABELS: tuple[str, ...] = (
    "Laughs",
    "Hype",
    "Troll",
    "Support",
    "Tension",
    "Curiosity",
)

TOP_VIBE_LABELS: dict[Vibe, str] = {
    "laughter_humor": "Laughs / Humor",
    "hype_pog": "Hype / Pog",
    "troll_sarcasm": "Troll / Sarcasm",
    "support_wholesome": "Support / Wholesome",
    "tension_drama": "Tension / Drama",
    "curiosity_context": "Curiosity / Context",
}

_HYPE_LEVELS = (
    "No hype or energy",
    "Mild reaction",
    "Clear excitement",
    "Strong hype / cheering",
    "Peak frenzy",
)

_TOPIC_SYNC_LEVELS = (
    "Completely different topic — chat ignores what the streamer said",
    "Mostly unrelated; only weak or accidental overlap",
    "Mixed — some on-topic messages, many not",
    "Same topic/moment — including jokes or trolls ABOUT that topic",
    "Strongly locked to what the streamer just said",
)

_BASE_QUESTIONS = {
    "intent": Choice(
        instructions="What is the primary intent of this live chat message?",
        criteria={
            "question": "Asks a question or seeks information from the streamer or chat",
            "hype/reaction": "Cheering, reacting, emotes, hype — no real question",
            "technical_issue": "Reports playback, audio, lag, buffering, or stream tech problems",
            "spam": "Spam, bots, scams, irrelevant promo, or nonsense flood",
        },
    ),
    "vibe": Choice(
        instructions=(
            "Entertainment/gaming live-chat vibe. Pick exactly one emotional axis "
            "for this message (Twitch/YouTube Live culture). Criteria and reasoning "
            "must be in English; chat slang in any language is fine as evidence."
        ),
        criteria={
            "laughter_humor": (
                "Laughter, memes, cringe — e.g. LOL, KEKW, LUL, XDD, funny fails"
            ),
            "hype_pog": (
                "High energy, epic plays, hype — e.g. POG, LETS GO, HYPE, clutch"
            ),
            "troll_sarcasm": (
                "Banter, gentle trolling, Fs in chat — e.g. F, RIP, skill issue, CLOWN, L"
            ),
            "support_wholesome": (
                "Love, GG, support, hearts — e.g. GG, love the stream, <3, wholesome"
            ),
            "tension_drama": (
                "Suspense, fear, intense moments — e.g. monkaS, NOOO, watch out, ???, oh no"
            ),
            "curiosity_context": (
                "Questions, context requests, theories — e.g. what happened?, "
                "what game is this?"
            ),
        },
    ),
    "hype": Score(
        instructions="How much live-chat hype or energy does this message show?",
        criteria=list(_HYPE_LEVELS),
    ),
}

_TOPIC_SYNC_QUESTIONS = {
    "topic_sync": Score(
        instructions=(
            "Compare the streamer's recent spoken words to recent live chat. "
            "Judge TOPICAL alignment only — same subject, moment, or referent. "
            "Tone does NOT matter: jokes, sarcasm, and trolling ABOUT what the "
            "streamer said still count as high alignment. "
            "Generic emotes with no topical anchor, or chat about something else, "
            "count as low. Reasoning in English; chat/speech may be any language."
        ),
        criteria=list(_TOPIC_SYNC_LEVELS),
    ),
}

_MAX_CONCURRENCY = 8


def empty_vibe_counts() -> dict[str, int]:
    return {axis: 0 for axis in VIBE_AXES}


def radar_from_vibe_counts(counts: dict[str, int]) -> dict[str, Any]:
    """Normalize vibe counts to radar % (non-spam only; caller must exclude spam)."""
    total = sum(int(counts.get(axis, 0) or 0) for axis in VIBE_AXES)
    if total <= 0:
        data = [0] * len(VIBE_AXES)
        return {
            "chart_type": "radar",
            "radar_data": {
                "labels": list(RADAR_LABELS),
                "datasets": [{"label": "Stream Vibe %", "data": data}],
            },
            "top_vibe": None,
            "vibe_counts": empty_vibe_counts(),
        }

    raw = [int(counts.get(axis, 0) or 0) for axis in VIBE_AXES]
    # Largest-remainder so integers sum to 100.
    exact = [c * 100.0 / total for c in raw]
    floors = [int(x) for x in exact]
    rem = 100 - sum(floors)
    order = sorted(range(len(exact)), key=lambda i: exact[i] - floors[i], reverse=True)
    data = floors[:]
    for i in order[:rem]:
        data[i] += 1

    top_idx = max(range(len(raw)), key=lambda i: (raw[i], -i))
    top_axis = VIBE_AXES[top_idx] if raw[top_idx] > 0 else None

    return {
        "chart_type": "radar",
        "radar_data": {
            "labels": list(RADAR_LABELS),
            "datasets": [{"label": "Stream Vibe %", "data": data}],
        },
        "top_vibe": TOP_VIBE_LABELS.get(top_axis) if top_axis else None,
        "vibe_counts": {axis: int(counts.get(axis, 0) or 0) for axis in VIBE_AXES},
    }


def _hype_to_0_100(raw_score: float) -> int:
    """Map TypeSafe Score (0..len(levels)-1) onto 0–100."""
    top = float(len(_HYPE_LEVELS) - 1)
    if top <= 0:
        return 0
    return int(max(0, min(100, round(float(raw_score) / top * 100))))


def _topic_sync_to_0_100(raw_score: float) -> int:
    top = float(len(_TOPIC_SYNC_LEVELS) - 1)
    if top <= 0:
        return 0
    return int(max(0, min(100, round(float(raw_score) / top * 100))))


async def classify_topic_sync(
    *,
    streamer_speech: str,
    chat_lines: list[str],
    client: AsyncTypeSafeClient,
) -> dict[str, Any]:
    """JEV topical sync: streamer speech vs recent chat (tone-agnostic)."""
    speech = (streamer_speech or "").strip()
    lines = [ln.strip() for ln in chat_lines if (ln or "").strip()]
    if not speech or not lines:
        return {
            "alignment_score": None,
            "alignment_label": None,
            "skipped": True,
        }

    # Cap payload size for the classifier.
    chat_blob = "\n".join(lines[-25:])
    if len(speech) > 2500:
        speech = speech[-2500:]
    if len(chat_blob) > 3500:
        chat_blob = chat_blob[-3500:]

    response = await client.system_one(
        state={
            "streamer_speech": speech,
            "recent_chat": chat_blob,
        },
        questions=_TOPIC_SYNC_QUESTIONS,
    )
    raw = float(response.scores["topic_sync"].score)
    score = _topic_sync_to_0_100(raw)

    # Local import avoids circular import at module load.
    from src.services.alignment_engine import label_for_score

    return {
        "alignment_score": score,
        "alignment_label": label_for_score(score),
        "skipped": False,
    }


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
        "hype_score": 0,
        "vibe": None,
    }
    if not text:
        return base

    async with sem:
        response = await client.system_one(
            state={"author": author, "message": text},
            questions=_BASE_QUESTIONS,
        )

    intent = response.choices["intent"].choice
    vibe = response.choices["vibe"].choice
    hype_raw = float(response.scores["hype"].score)

    return {
        **base,
        "intent": intent,
        "vibe": vibe if vibe in VIBE_AXES else None,
        "hype_score": _hype_to_0_100(hype_raw),
        "intent_confidence": float(response.choices["intent"].confidence or 0),
        "vibe_confidence": float(response.choices["vibe"].confidence or 0),
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
        radar = radar_from_vibe_counts(empty_vibe_counts())
        return {
            "classifications": [],
            "hype_score": 0,
            "spam_count": 0,
            "message_count": 0,
            **radar,
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
    vibe_counts = empty_vibe_counts()
    hype_values: list[int] = []
    spam_count = 0

    for item in results:
        classifications.append(item)
        if item.get("intent") == "spam":
            spam_count += 1
            continue
        hype_values.append(int(item.get("hype_score") or 0))
        vibe = item.get("vibe")
        if vibe in vibe_counts:
            vibe_counts[vibe] += 1

    avg_hype = int(round(sum(hype_values) / len(hype_values))) if hype_values else 0
    radar = radar_from_vibe_counts(vibe_counts)

    return {
        "classifications": classifications,
        "hype_score": avg_hype,
        "spam_count": spam_count,
        "message_count": len(messages),
        **radar,
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
                    "hype_score": 0,
                    "vibe": None,
                    "error": str(result),
                }
            )
        else:
            out.append(result)
    return out
