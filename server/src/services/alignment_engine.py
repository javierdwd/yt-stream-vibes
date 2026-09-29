"""Streamer↔chat topical alignment labels and text-window helpers."""

from __future__ import annotations

from typing import Any, Literal

AlignmentLabel = Literal[
    "In Perfect Sync",
    "Partial Engagement",
    "Off Topic / Disconnected",
]

# How much recent speech/chat to feed JEV / word cloud / theme.
SPEECH_WINDOW_S = 20.0
CHAT_WINDOW_S = 120.0
MAX_CHAT_LINES = 150


def label_for_score(score: int) -> AlignmentLabel:
    if score > 75:
        return "In Perfect Sync"
    if score >= 40:
        return "Partial Engagement"
    return "Off Topic / Disconnected"


def join_recent_speech(
    chunks: list[tuple[float, str]],
    *,
    now: float,
    window_s: float = SPEECH_WINDOW_S,
) -> str:
    cutoff = now - window_s
    parts = [text.strip() for ts, text in chunks if ts >= cutoff and (text or "").strip()]
    return " ".join(parts).strip()


def recent_chat_lines(
    snippets: list[Any],
    *,
    now: float,
    window_s: float = CHAT_WINDOW_S,
    max_lines: int = MAX_CHAT_LINES,
) -> list[str]:
    """Return newest-last chat lines within the time window (capped)."""
    cutoff = now - window_s
    lines: list[str] = []
    for sample in snippets:
        ts = getattr(sample, "ts", None)
        if ts is None or ts < cutoff:
            continue
        line = (getattr(sample, "line", None) or "").strip()
        if line:
            lines.append(line)
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return lines
