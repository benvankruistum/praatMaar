"""Deterministic transcript heuristics that propose Meeting State changes."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict, deque
from uuid import uuid4

from modules.capabilities.speech_to_text import TranscriptDelta

from .config import MeetingBuddyConfig
from .hint_text import clean_question_text, question_is_substantial
from .state import ActionItemStatus, MeetingState, Question, QuestionStatus, TopicStatus
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
        self._source_windows: dict[str, tuple[int, int]] = {}

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

        looks_like_question = bool("?" in delta.text or _QUESTION_PATTERN.search(normalized))
        proposals = self._topic_proposals(delta, state, config, now_s, window_text)
        proposals.extend(
            self._question_proposals(
                delta,
                state,
                config,
                now_s,
                normalized,
                looks_like_question,
            )
        )
        if looks_like_question and not self._has_similar_open_question(state, normalized):
            cleaned = clean_question_text(delta.text.strip())
            if question_is_substantial(cleaned):
                proposals.append(
                    self._proposal(
                        "add_question",
                        delta,
                        state,
                        now_s,
                        {"text": cleaned, "created_at": now_s},
                    )
                )
        self._source_windows[f"{delta.session_id}:{delta.sequence}"] = (
            delta.start_ms,
            delta.end_ms,
        )
        if _ACTION_PATTERN.search(normalized) and not self._has_similar_candidate_action(
            state, normalized
        ):
            proposals.append(
                self._proposal(
                    "add_action",
                    delta,
                    state,
                    now_s,
                    {
                        "description": delta.text.strip(),
                        "owner": "UNKNOWN",
                        "created_at": now_s,
                    },
                )
            )
        return proposals

    @staticmethod
    def _has_similar_open_question(state: MeetingState, normalized: str) -> bool:
        return any(
            question.status == QuestionStatus.OPEN
            and _is_highly_similar(_normalize(question.text), normalized)
            for question in state.questions
        )

    @staticmethod
    def _has_similar_candidate_action(state: MeetingState, normalized: str) -> bool:
        return any(
            action.status == ActionItemStatus.CANDIDATE
            and _is_highly_similar(_normalize(action.description), normalized)
            for action in state.action_items
        )

    def _question_proposals(
        self,
        delta: TranscriptDelta,
        state: MeetingState,
        config: MeetingBuddyConfig,
        now_s: float,
        normalized: str,
        looks_like_question: bool,
    ) -> list[StateProposal]:
        delta_id = f"{delta.session_id}:{delta.sequence}"
        delta_tokens = set(_tokens(normalized))
        proposals = []
        for question in state.questions:
            question_tokens = set(_tokens(_normalize(question.text)))
            age = now_s - question.created_at if question.created_at is not None else 0
            if (
                question.status != QuestionStatus.OPEN
                or question.source_delta_id == delta_id
                or age > config.topic_match_window_s
                or _normalize(question.text) == normalized
                or (
                    looks_like_question
                    and (
                        _is_highly_similar(_normalize(question.text), normalized)
                        or self._substantially_overlaps_source(question, delta)
                    )
                )
                or not _has_sufficient_overlap(question_tokens, delta_tokens, config)
            ):
                continue
            proposals.append(
                self._proposal(
                    "update_question",
                    delta,
                    state,
                    now_s,
                    {
                        "question_id": question.id,
                        "status": QuestionStatus.POSSIBLY_ANSWERED.value,
                        "resolved_at": now_s,
                    },
                )
            )
        return proposals

    def _substantially_overlaps_source(self, question: Question, delta: TranscriptDelta) -> bool:
        source_window = self._source_windows.get(question.source_delta_id or "")
        if source_window is None:
            return False
        source_start, source_end = source_window
        overlap_ms = max(0, min(source_end, delta.end_ms) - max(source_start, delta.start_ms))
        shorter_duration_ms = min(source_end - source_start, delta.end_ms - delta.start_ms)
        return shorter_duration_ms > 0 and overlap_ms / shorter_duration_ms >= 0.5

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


def _is_highly_similar(left: str, right: str) -> bool:
    if left == right:
        return True
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return False
    matched = left_tokens & right_tokens
    return (
        len(matched) >= 3
        and len(matched) / min(len(left_tokens), len(right_tokens)) >= 0.8
        and len(matched) / len(left_tokens | right_tokens) >= 0.6
    )


def _has_sufficient_overlap(
    expected_tokens: set[str],
    actual_tokens: set[str],
    config: MeetingBuddyConfig,
) -> bool:
    if not expected_tokens:
        return False
    matched = expected_tokens & actual_tokens
    return (
        len(matched) >= config.matched_tokens_min
        and len(matched) / len(expected_tokens) >= config.topic_match_score
    )
