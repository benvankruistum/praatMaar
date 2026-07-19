from modules._builtin.meeting_buddy.prep import parse_agenda


def test_parse_strips_bullets_and_numbers() -> None:
    text = (
        "1. Stand van zaken planning\n2. Budget\n- Beveiligingsrisico's\nBesluit over livegang\n\n"
    )

    assert parse_agenda(text) == [
        "Stand van zaken planning",
        "Budget",
        "Beveiligingsrisico's",
        "Besluit over livegang",
    ]


def test_parse_ignores_empty_bullet_lines_and_trims_content() -> None:
    assert parse_agenda("  *   Scope  \n3)   \n• Planning\n") == ["Scope", "Planning"]
