"""Ollama-backed SemanticAnalysisCapability provider."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from modules.capabilities.semantic_analysis import (
    KIND_AGENDA_REVIEW,
    KIND_FINAL_SUMMARY,
    KIND_RUNNING_SUMMARY,
    AnalysisRequest,
    AnalysisResult,
)

from .ollama_client import OllamaClient, OllamaError

log = logging.getLogger("praatmaar.local_llm.provider")

_LANG_LABEL = {"nl": "Nederlands", "en": "English", "de": "Deutsch"}
_READY_TTL_S = 30.0
_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


class OllamaSemanticAnalysis:
    """Implements ``ai.semantic_analysis`` via a local Ollama model."""

    def __init__(self, client: OllamaClient, *, model: str) -> None:
        self._client = client
        self._model = model
        self._ready_cache: bool | None = None
        self._ready_checked_at = 0.0

    @property
    def model(self) -> str:
        return self._model

    def is_ready(self) -> bool:
        now = time.monotonic()
        if self._ready_cache is not None and (now - self._ready_checked_at) < _READY_TTL_S:
            return self._ready_cache
        try:
            ready = self._client.has_model(self._model)
        except OllamaError:
            ready = False
        self._ready_cache = ready
        self._ready_checked_at = now
        return ready

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        if request.kind == KIND_RUNNING_SUMMARY:
            text = self._running_summary(request)
            return AnalysisResult(kind=KIND_RUNNING_SUMMARY, text=text)
        if request.kind == KIND_FINAL_SUMMARY:
            text = self._final_summary(request)
            return AnalysisResult(kind=KIND_FINAL_SUMMARY, text=text)
        if request.kind == KIND_AGENDA_REVIEW:
            data = self._agenda_review(request)
            return AnalysisResult(
                kind=KIND_AGENDA_REVIEW,
                text=json.dumps(data, ensure_ascii=False),
                data=data,
            )
        raise ValueError(f"Onbekend analyse-kind: {request.kind!r}")

    def analyze_delta(self, delta: Any, state_snapshot: Any) -> list[Any]:
        return []

    def _running_summary(self, request: AnalysisRequest) -> str:
        lang = _LANG_LABEL.get(request.language, request.language or "Nederlands")
        previous = (request.previous_summary or "").strip()
        transcript = request.transcript.strip()
        if not transcript:
            return previous

        system = (
            f"Je bent een beknopte notulist. Schrijf in het {lang}. "
            "Geef alleen een bijgewerkte lopende samenvatting als 3 tot 5 bullets. "
            "Elke regel begint met '- '. Geen markdown-koppen, geen nummers, "
            "geen inleiding of slotzin, geen labels. Vervang de vorige set volledig. "
            "Noem besluiten, acties en open agendapunten waar relevant."
        )
        user_parts = []
        agenda = (request.context or {}).get("agenda") or []
        open_titles = (request.context or {}).get("open_titles") or []
        if agenda:
            user_parts.append(f"Agenda (titel, status):\n{json.dumps(agenda, ensure_ascii=False)}")
        if open_titles:
            user_parts.append(f"Nog niet besproken: {', '.join(open_titles)}")
        if previous:
            user_parts.append(f"Vorige samenvatting:\n{previous}")
        user_parts.append(f"Nieuw transcript (sinds vorige samenvatting):\n{transcript}")
        user_parts.append(
            "Werk de lopende samenvatting bij op basis van het nieuwe transcript. "
            "Antwoord met precies 3 tot 5 regels die met '- ' beginnen."
        )
        content = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            temperature=0.2,
        )
        return content.strip()

    def _final_summary(self, request: AnalysisRequest) -> str:
        lang = _LANG_LABEL.get(request.language, request.language or "Nederlands")
        transcript = request.transcript.strip()
        if not transcript:
            return (request.previous_summary or "").strip()
        context = request.context or {}
        agenda = context.get("agenda") or []
        open_titles = context.get("open_titles") or []
        questions = context.get("open_questions") or []
        system = (
            f"Je bent een meeting-notulist. Schrijf in het {lang}. "
            "Maak een eind-samenvatting van de meeting in 5 tot 8 bullets (regels met '- '). "
            "Behandel: besproken agendapunten, besluiten, acties, open punten en open vragen. "
            "Geen markdown-koppen, geen inleiding."
        )
        user_parts = [
            f"Volledig transcript:\n{transcript}",
        ]
        if agenda:
            user_parts.append(f"Agenda (titel, status):\n{json.dumps(agenda, ensure_ascii=False)}")
        if open_titles:
            user_parts.append(f"Agenda nog open: {', '.join(open_titles)}")
        if questions:
            user_parts.append(f"Open vragen van anderen: {', '.join(questions)}")
        previous = (request.previous_summary or "").strip()
        if previous:
            user_parts.append(f"Lopende samenvatting tijdens de meeting:\n{previous}")
        content = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            temperature=0.2,
        )
        return content.strip()

    def _agenda_review(self, request: AnalysisRequest) -> dict[str, Any]:
        lang = _LANG_LABEL.get(request.language, request.language or "Nederlands")
        context = request.context or {}
        topics = context.get("topics", [])
        phase = context.get("phase", "body")
        system = (
            f"Je bent een meeting-assistent. Antwoord uitsluitend met JSON in het {lang}-domein. "
            "Schema: "
            '{"phase":"opening|body|closing",'
            '"topic_updates":[{"topic_id":"...","status":"treated|confirmed"}],'
            '"questions":["..."]}. '
            "Regels: treated alleen bij substantiële bespreking (niet noemen/doorlopen). "
            "confirmed alleen als het punt al sequential was en opnieuw inhoudelijk besproken is. "
            "In phase opening: geen topic_updates voor latere agendapunten dan het eerste. "
            "questions: alleen open vragen van anderen (niet de host/me), herformuleerd tot één zin. "
            "Geen markdown, geen uitleg buiten JSON."
        )
        user = (
            f"Huidige fase: {phase}\n"
            f"Agendapunten (id, titel, status):\n{json.dumps(topics, ensure_ascii=False)}\n\n"
            f"Transcript (regels kunnen [me]/[other]/[unknown] hebben):\n"
            f"{request.transcript.strip()}"
        )
        content = self._client.chat(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            format_json=True,
        )
        return _parse_agenda_json(content)


def _parse_agenda_json(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if not text:
        return {"phase": "body", "topic_updates": [], "questions": []}
    match = _JSON_BLOCK.search(text)
    raw = match.group(0) if match else text
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("agenda_review: ongeldige JSON van model")
        return {"phase": "body", "topic_updates": [], "questions": []}
    if not isinstance(data, dict):
        return {"phase": "body", "topic_updates": [], "questions": []}
    phase = str(data.get("phase", "body")).strip().lower()
    if phase not in {"opening", "body", "closing"}:
        phase = "body"
    updates = data.get("topic_updates") or []
    if not isinstance(updates, list):
        updates = []
    questions = data.get("questions") or []
    if not isinstance(questions, list):
        questions = []
    return {
        "phase": phase,
        "topic_updates": [
            {
                "topic_id": str(item.get("topic_id", "")),
                "status": str(item.get("status", "")).strip().lower(),
            }
            for item in updates
            if isinstance(item, dict) and item.get("topic_id")
        ],
        "questions": [str(q).strip() for q in questions if str(q).strip()],
    }
