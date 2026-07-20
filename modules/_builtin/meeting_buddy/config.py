"""Typed Meeting Buddy configuration loaded from shipped and user YAML."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

import yaml

from modules.settings_store import module_dir

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

    known_fields = {field.name for field in fields(MeetingBuddyConfig)}
    values = {key: value for key, value in defaults.items() if key in known_fields}
    return MeetingBuddyConfig(**values)


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Meeting Buddy config must be a mapping: {path}")
    return raw
