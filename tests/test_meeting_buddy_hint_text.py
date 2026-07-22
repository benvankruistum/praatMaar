from modules._builtin.meeting_buddy.hint_text import (
    clean_question_text,
    format_question_hint,
    question_is_substantial,
)


def test_clean_question_text_strips_meta_prefix() -> None:
    assert clean_question_text("De vraag is hoe we dit oplossen?") == "hoe we dit oplossen?"


def test_question_is_substantial_rejects_short_fragments() -> None:
    assert not question_is_substantial("de vraag is")
    assert not question_is_substantial("Hoe gaan")
    assert question_is_substantial("Hoe gaan we dit volgende kwartaal oplossen?")


def test_format_question_hint_uses_full_sentence() -> None:
    message = format_question_hint("Wanneer leveren we de nieuwe versie op?")
    assert "Deze vraag staat nog open:" in message
    assert "Wanneer leveren we de nieuwe versie op?" in message
