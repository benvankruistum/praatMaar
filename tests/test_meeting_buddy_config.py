from pathlib import Path

from modules._builtin.meeting_buddy.config import (
    MeetingBuddyConfig,
    load_meeting_buddy_config,
)


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
