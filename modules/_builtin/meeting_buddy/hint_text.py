"""Format and filter hint source text from raw transcript chunks."""

from __future__ import annotations

import re

_META_QUESTION_PREFIX = re.compile(
    r"^(?:de|mijn|onze|jouw|the|my|our|your)\s+(?:vraag|question)\s+is\s+",
    re.IGNORECASE,
)
_TRAILING_ELLIPSIS = re.compile(r"[.\u2026…\s]+$")


def clean_question_text(text: str) -> str:
    """Strip meta prefixes and trailing ellipsis from a transcript fragment."""

    cleaned = text.strip()
    cleaned = _META_QUESTION_PREFIX.sub("", cleaned).strip()
    cleaned = _TRAILING_ELLIPSIS.sub("", cleaned).strip()
    return cleaned


def question_is_substantial(text: str) -> bool:
    """Ignore fragments that are too short to be useful as meeting hints."""

    cleaned = clean_question_text(text)
    if len(cleaned) < 12:
        return False
    words = [word for word in re.findall(r"\w+", cleaned, flags=re.UNICODE) if len(word) > 1]
    if len(words) >= 4:
        return True
    return "?" in cleaned and len(cleaned) >= 20


def truncate_for_hint(text: str, *, limit: int = 140) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_question_hint(text: str) -> str:
    display = truncate_for_hint(clean_question_text(text))
    return f"Deze vraag staat nog open: «{display}»"


def format_topic_hint(title: str) -> str:
    display = truncate_for_hint(title.strip())
    return f"Agendapunt nog niet besproken: «{display}»"


def format_action_hint(description: str) -> str:
    display = truncate_for_hint(clean_question_text(description))
    return f"Mogelijk actiepunt zonder eigenaar: «{display}»"
