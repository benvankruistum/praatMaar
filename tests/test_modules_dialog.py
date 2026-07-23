"""Tests for modules dialog helpers."""

from __future__ import annotations

from modules_dialog import module_shows_action_buttons


def test_module_shows_action_buttons_when_enabled() -> None:
    assert module_shows_action_buttons(
        "meeting_buddy",
        has_actions=True,
        on_module_action=lambda _mid, _aid: None,
        enabled_module_ids={"meeting_buddy"},
    )


def test_module_shows_action_buttons_hidden_without_actions() -> None:
    assert not module_shows_action_buttons(
        "meeting_buddy",
        has_actions=False,
        on_module_action=lambda _mid, _aid: None,
        enabled_module_ids={"meeting_buddy"},
    )


def test_module_shows_action_buttons_hidden_when_disabled() -> None:
    assert not module_shows_action_buttons(
        "meeting_buddy",
        has_actions=True,
        on_module_action=lambda _mid, _aid: None,
        enabled_module_ids=set(),
    )


def test_module_shows_action_buttons_hidden_without_callback() -> None:
    assert not module_shows_action_buttons(
        "meeting_buddy",
        has_actions=True,
        on_module_action=None,
        enabled_module_ids={"meeting_buddy"},
    )
