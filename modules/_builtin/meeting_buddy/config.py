"""Typed Meeting Buddy configuration loaded from shipped and user YAML."""

from __future__ import annotations

import logging
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

import yaml

from modules.settings_store import load_config as load_module_json
from modules.settings_store import module_dir, save_config

log = logging.getLogger(__name__)

_DEFAULTS_PATH = Path(__file__).resolve().parents[2] / "defaults" / "meeting-buddy.yaml"
_MAPPING_FIELDS = frozenset({"hint_cooldown", "hint_min_wait_s"})


@dataclass(frozen=True)
class MeetingBuddyConfig:
    topic_match_score: float
    matched_tokens_min: int
    topic_match_window_s: float
    question_hint_min_wait_s: float
    question_hint_cooldown_s: float
    question_hint_suppress_after_s: float
    hint_cooldown: dict[str, float]
    hint_min_wait_s: dict[str, float]
    max_visible_hints: int
    min_hint_confidence: float
    max_whisper_queue_duration_s: float
    max_audio_buffer_duration_s: float
    enable_loopback: bool = False
    loopback_device: int | None = None
    mic_mix_gain: float = 0.5
    loopback_mix_gain: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.topic_match_score <= 1.0:
            raise ValueError("topic_match_score must be between 0 and 1")
        if not 0 <= self.max_visible_hints <= 3:
            raise ValueError("max_visible_hints must be between 0 and 3")
        if not 0.0 <= self.min_hint_confidence <= 1.0:
            raise ValueError("min_hint_confidence must be between 0 and 1")
        if self.max_whisper_queue_duration_s <= 0:
            raise ValueError("max_whisper_queue_duration_s must be positive")
        if self.max_audio_buffer_duration_s <= 0:
            raise ValueError("max_audio_buffer_duration_s must be positive")
        if self.max_audio_buffer_duration_s < self.max_whisper_queue_duration_s:
            raise ValueError("max_audio_buffer_duration_s must be >= max_whisper_queue_duration_s")
        for key, value in self.hint_cooldown.items():
            if value < 0:
                raise ValueError(f"hint_cooldown.{key} must be non-negative")
        for key, value in self.hint_min_wait_s.items():
            if value < 0:
                raise ValueError(f"hint_min_wait_s.{key} must be non-negative")
        for name, value in (
            ("mic_mix_gain", self.mic_mix_gain),
            ("loopback_mix_gain", self.loopback_mix_gain),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

    @classmethod
    def defaults(cls) -> MeetingBuddyConfig:
        """Load the defaults shipped with the application."""

        return cls(**_read_yaml_mapping(_DEFAULTS_PATH))

    def replace(self, **changes: Any) -> MeetingBuddyConfig:
        """Return a copy with selected values changed."""

        return replace(self, **changes)


def load_meeting_buddy_config(app_dir: Path) -> MeetingBuddyConfig:
    """Merge the optional per-user YAML over the shipped defaults."""

    defaults = _read_yaml_mapping(_DEFAULTS_PATH)
    user_path = module_dir(app_dir, "meeting-buddy") / "meeting-buddy.yaml"
    if user_path.is_file():
        overrides = _read_yaml_mapping(user_path)
        for key in _MAPPING_FIELDS:
            if key in overrides:
                overrides[key] = {**defaults[key], **overrides[key]}
        defaults.update(overrides)

    json_overrides = load_module_json(app_dir, "meeting-buddy")
    for key in ("enable_loopback", "loopback_device"):
        if key in json_overrides:
            defaults[key] = json_overrides[key]

    known_fields = {field.name for field in fields(MeetingBuddyConfig)}
    values = {key: value for key, value in defaults.items() if key in known_fields}
    try:
        return MeetingBuddyConfig(**values)
    except (TypeError, ValueError) as exc:
        log.warning(
            "Invalid Meeting Buddy config; falling back to defaults: %s",
            exc,
        )
        return MeetingBuddyConfig.defaults()


def save_meeting_buddy_preferences(
    app_dir: Path,
    *,
    enable_loopback: bool,
    loopback_device: int | None,
    transcripts_directory: str | None = None,
    live_summary_enabled: bool | None = None,
    llm_chunk_interval_s: float | None = None,
    llm_chunk_min_new_chars: int | None = None,
) -> None:
    """Persist loopback UI choices and optional transcript folder in ``config.json``."""

    current = load_module_json(app_dir, "meeting-buddy")
    current["enable_loopback"] = enable_loopback
    current["loopback_device"] = loopback_device
    if transcripts_directory is None or not str(transcripts_directory).strip():
        current.pop("transcripts_directory", None)
    else:
        current["transcripts_directory"] = str(transcripts_directory).strip()
    if live_summary_enabled is not None:
        current["live_summary_enabled"] = bool(live_summary_enabled)
    if llm_chunk_interval_s is not None:
        current["llm_chunk_interval_s"] = float(llm_chunk_interval_s)
    if llm_chunk_min_new_chars is not None:
        current["llm_chunk_min_new_chars"] = int(llm_chunk_min_new_chars)
    save_config(app_dir, "meeting-buddy", current)


def load_transcripts_directory(app_dir: Path) -> str | None:
    """Return configured transcript folder override, or ``None`` for the default."""

    raw = load_module_json(app_dir, "meeting-buddy").get("transcripts_directory")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return raw.strip()


def load_live_summary_prefs(app_dir: Path) -> dict[str, Any]:
    """Live-summary prefs from module ``config.json`` (defaults if missing)."""

    data = load_module_json(app_dir, "meeting-buddy")
    interval = data.get("llm_chunk_interval_s", 60)
    min_chars = data.get("llm_chunk_min_new_chars", 200)
    try:
        interval_f = float(interval)
    except (TypeError, ValueError):
        interval_f = 60.0
    try:
        min_chars_i = int(min_chars)
    except (TypeError, ValueError):
        min_chars_i = 200
    return {
        "live_summary_enabled": bool(data.get("live_summary_enabled", False)),
        "llm_chunk_interval_s": max(15.0, interval_f),
        "llm_chunk_min_new_chars": max(50, min_chars_i),
    }


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Meeting Buddy config must be a mapping: {path}")
    return raw
