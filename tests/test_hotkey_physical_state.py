"""Sneltoets vuurt alleen als de toetsen ook fysiek ingedrukt zijn.

Achtergrond: `pressed_tokens` werd opgebouwd uit press/release-paren. Levert een
release een ándere token op dan de press (andere vk, ander teken door Shift, of
een vk die niet in de tabel staat), dan blijft de press-token voor altijd staan.
Met sneltoets Shift+Esc vuurde daarna alléén Shift de toggle. Zie #44 voor een
eerdere, gedeeltelijke fix; deze test dekt de hele klasse.
"""

from __future__ import annotations

import hotkeys


def test_token_to_vk_covers_modifiers() -> None:
    assert hotkeys.token_to_vk("shift") == 0x10
    assert hotkeys.token_to_vk("ctrl") == 0x11
    assert hotkeys.token_to_vk("alt") == 0x12
    assert hotkeys.token_to_vk("cmd") == 0x5B


def test_token_to_vk_covers_letters_and_digits() -> None:
    assert hotkeys.token_to_vk("a") == 0x41
    assert hotkeys.token_to_vk("z") == 0x5A
    assert hotkeys.token_to_vk("0") == 0x30
    assert hotkeys.token_to_vk("9") == 0x39


def test_token_to_vk_covers_specials_and_function_keys() -> None:
    assert hotkeys.token_to_vk("esc") == 0x1B
    assert hotkeys.token_to_vk("space") == 0x20
    assert hotkeys.token_to_vk("enter") == 0x0D
    assert hotkeys.token_to_vk("f9") == 0x78


def test_token_to_vk_is_none_for_unknown() -> None:
    assert hotkeys.token_to_vk("onbekend") is None
    assert hotkeys.token_to_vk("") is None
    assert hotkeys.token_to_vk("vk1234") is None


def test_roundtrip_with_key_to_token_vk_table() -> None:
    # Elke token uit de vk->token-tabel moet terug te mappen zijn.
    for vk, token in hotkeys._VK_TO_TOKEN.items():
        assert hotkeys.token_to_vk(token) == vk, token


# --- zelfherstel in dictation.hotkey_is_pressed ---------------------------


def _reset(dictation, tokens: set[str]) -> None:
    dictation.HOTKEY_TOKENS = set(tokens)
    dictation.pressed_tokens.clear()


def test_hotkey_fires_when_all_keys_are_physically_down(monkeypatch) -> None:
    import dictation

    _reset(dictation, {"shift", "esc"})
    dictation.pressed_tokens.update({"shift", "esc"})
    monkeypatch.setattr(dictation.host, "keys_physically_down", lambda tokens: set(tokens))

    assert dictation.hotkey_is_pressed() is True


def test_stale_token_does_not_fire_and_is_purged(monkeypatch) -> None:
    # Kern van de bug: "esc" bleef hangen; alleen Shift indrukken vuurde toch.
    import dictation

    _reset(dictation, {"shift", "esc"})
    dictation.pressed_tokens.update({"shift", "esc"})  # esc is een spook
    monkeypatch.setattr(dictation.host, "keys_physically_down", lambda _tokens: {"shift"})

    assert dictation.hotkey_is_pressed() is False
    # Zelfherstel: het spook is opgeruimd, zodat de volgende druk weer klopt.
    assert "esc" not in dictation.pressed_tokens
    assert "shift" in dictation.pressed_tokens


def test_falls_back_to_bookkeeping_when_platform_cannot_tell(monkeypatch) -> None:
    # Linux/macOS zonder statusbron: gedrag blijft zoals het was.
    import dictation

    _reset(dictation, {"shift", "esc"})
    dictation.pressed_tokens.update({"shift", "esc"})
    monkeypatch.setattr(dictation.host, "keys_physically_down", lambda _tokens: None)

    assert dictation.hotkey_is_pressed() is True


def test_incomplete_combination_never_queries_the_platform(monkeypatch) -> None:
    import dictation

    calls: list[object] = []

    def spy(tokens):
        calls.append(tokens)
        return set(tokens)

    _reset(dictation, {"shift", "esc"})
    dictation.pressed_tokens.add("shift")
    monkeypatch.setattr(dictation.host, "keys_physically_down", spy)

    assert dictation.hotkey_is_pressed() is False
    assert calls == [], "geen OS-call nodig zolang de combinatie al incompleet is"


def test_empty_hotkey_never_fires(monkeypatch) -> None:
    import dictation

    _reset(dictation, set())
    monkeypatch.setattr(dictation.host, "keys_physically_down", lambda _t: None)
    assert dictation.hotkey_is_pressed() is False


def test_wait_for_modifiers_purges_stale_tokens(monkeypatch) -> None:
    """Tweede symptoom van dezelfde oorzaak: 3 seconden vertraging bij plakken.

    wait_until_modifier_keys_released() keek ook naar pressed_tokens. Bleef daar
    een spook in staan, dan wachtte élke plak-actie de volledige time-out uit.
    """

    import dictation

    _reset(dictation, {"shift", "esc"})
    dictation.pressed_tokens.update({"shift", "esc"})  # beide spoken
    monkeypatch.setattr(dictation.host, "keys_physically_down", lambda _t: set())

    import time

    started = time.monotonic()
    dictation.wait_until_modifier_keys_released(timeout=3.0)
    duur = time.monotonic() - started

    assert duur < 1.0, f"mag niet de time-out uitzitten, duurde {duur:.2f}s"
    assert not dictation.pressed_tokens
