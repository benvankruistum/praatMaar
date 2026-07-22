from pathlib import Path

from modules._builtin.meeting_buddy.config import (
    MeetingBuddyConfig,
    load_meeting_buddy_config,
    save_meeting_buddy_preferences,
)
from modules.settings_store import save_config


def test_defaults_load_without_user_file(tmp_path: Path) -> None:
    cfg = load_meeting_buddy_config(tmp_path)

    assert cfg.max_visible_hints == 3
    assert cfg.topic_match_score == 0.55
    assert cfg.min_hint_confidence == 0.5
    assert cfg.enable_loopback is True
    assert cfg.loopback_device is None


def test_user_file_overrides_defaults_and_nested_values(tmp_path: Path) -> None:
    config_dir = tmp_path / "meeting-buddy"
    config_dir.mkdir()
    (config_dir / "meeting-buddy.yaml").write_text(
        "max_visible_hints: 2\nhint_cooldown:\n  question_open: 15\n",
        encoding="utf-8",
    )

    cfg = load_meeting_buddy_config(tmp_path)

    assert cfg.max_visible_hints == 2
    assert cfg.hint_cooldown["question_open"] == 15
    assert cfg.hint_cooldown["topic_not_discussed"] == 180


def test_config_replace_returns_new_dataclass() -> None:
    original = MeetingBuddyConfig.defaults()

    updated = original.replace(max_visible_hints=1)

    assert original.max_visible_hints == 3
    assert updated.max_visible_hints == 1


def test_config_json_overrides_loopback_preferences(tmp_path: Path) -> None:
    save_config(
        tmp_path,
        "meeting-buddy",
        {"loopback_device": 7, "enable_loopback": False},
    )

    cfg = load_meeting_buddy_config(tmp_path)

    assert cfg.loopback_device == 7
    assert cfg.enable_loopback is False


def test_save_meeting_buddy_preferences_persists_loopback_fields(tmp_path: Path) -> None:
    save_meeting_buddy_preferences(
        tmp_path,
        enable_loopback=True,
        loopback_device=3,
    )

    cfg = load_meeting_buddy_config(tmp_path)

    assert cfg.loopback_device == 3
    assert cfg.enable_loopback is True


def test_invalid_user_yaml_falls_back_to_defaults(tmp_path: Path) -> None:
    config_dir = tmp_path / "meeting-buddy"
    config_dir.mkdir()
    (config_dir / "meeting-buddy.yaml").write_text("max_visible_hints: 9\n", encoding="utf-8")

    cfg = load_meeting_buddy_config(tmp_path)

    assert cfg.max_visible_hints == 3
