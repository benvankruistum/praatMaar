"""Deterministic transcript heuristics that propose Meeting State changes."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict, deque
from uuid import uuid4

from modules.capabilities.speech_to_text import TranscriptDelta

from .config import MeetingBuddyConfig
from .state import MeetingState, TopicStatus
from .state_service import StateProposal

_STOPWORDS = {
    "aan",
    "de",
    "een",
    "en",
    "het",
    "in",
    "met",
    "of",
    "om",
    "op",
    "te",
    "van",
    "voor",
}
_QUESTION_PATTERN = re.compile(
    r"\b(?:wie|wat|waar|wanneer|waarom|hoe|kunnen we|moeten we|is het|"
    r"hebben we|wat doen we met)\b"
)
_ACTION_PATTERN = re.compile(r"\b(?:ik pak|jij doet|kun jij|actiepunt|we moeten nog|laten we)\b")


class HeuristicsEngine:
    """Turn final transcript deltas into confidence-carrying proposals."""

    def __init__(self) -> None:
        self._recent_text: dict[str, deque[tuple[float, str]]] = defaultdict(deque)

    def proposals_for(
        self,
        delta: TranscriptDelta,
        state: MeetingState,
        config: MeetingBuddyConfig,
        now_s: float,
    ) -> list[StateProposal]:
        if not delta.is_final or not delta.text.strip():
            return []

        normalized = _normalize(delta.text)
        recent = self._recent_text[state.meeting_session_id]
        recent.append((now_s, normalized))
        cutoff = now_s - config.topic_match_window_s
        while recent and recent[0][0] < cutoff:
            recent.popleft()
        window_text = " ".join(text for _, text in recent)

        proposals = self._topic_proposals(delta, state, config, now_s, window_text)
        if "?" in delta.text or _QUESTION_PATTERN.search(normalized):
            proposals.append(
                self._proposal(
                    "add_question",
                    delta,
                    state,
                    now_s,
                    {"text": delta.text.strip(), "created_at": now_s},
                )
            )
        if _ACTION_PATTERN.search(normalized):
            proposals.append(
                self._proposal(
                    "add_action",
                    delta,
                    state,
                    now_s,
                    {
                        "description": delta.text.strip(),
                        "owner": "UNKNOWN",
                    },
                )
            )
        return proposals

    def _topic_proposals(
        self,
        delta: TranscriptDelta,
        state: MeetingState,
        config: MeetingBuddyConfig,
        now_s: float,
        window_text: str,
    ) -> list[StateProposal]:
        window_tokens = set(_tokens(window_text))
        proposals = []
        for topic in state.topics:
            if topic.status != TopicStatus.OPEN:
                continue
            normalized_title = _normalize(topic.title)
            topic_tokens = set(_tokens(normalized_title))
            if not topic_tokens:
                continue
            matched = topic_tokens & window_tokens
            score = len(matched) / len(topic_tokens)
            full_phrase_match = len(normalized_title) >= 3 and normalized_title in window_text
            enough_tokens = len(matched) >= config.matched_tokens_min or full_phrase_match
            if score >= config.topic_match_score and enough_tokens:
                proposals.append(
                    self._proposal(
                        "mark_topic_discussed",
                        delta,
                        state,
                        now_s,
                        {"topic_id": topic.id, "matched_at": now_s},
                        confidence=min(delta.confidence, score),
                    )
                )
        return proposals

    @staticmethod
    def _proposal(
        proposal_type: str,
        delta: TranscriptDelta,
        state: MeetingState,
        now_s: float,
        payload: dict[str, object],
        *,
        confidence: float | None = None,
    ) -> StateProposal:
        return StateProposal(
            proposal_id=f"heuristic-{uuid4()}",
            meeting_session_id=state.meeting_session_id,
            type=proposal_type,
            payload=payload,
            source_delta_ids=(f"{delta.session_id}:{delta.sequence}",),
            confidence=delta.confidence if confidence is None else confidence,
            created_at=now_s,
        )


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", without_marks))


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(token for token in text.split() if token not in _STOPWORDS)
