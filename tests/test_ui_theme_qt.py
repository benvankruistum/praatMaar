from ui.theme import TOKENS, build_qss


def test_tokens_include_canvas_accent():
    assert TOKENS["accent"].upper() == "#0F6CBD"


def test_tokens_include_canvas_control_colours():
    assert TOKENS["border_strong"].upper() == "#D2D8DF"
    assert TOKENS["hover"].upper() == "#EFF2F6"
    assert TOKENS["text_secondary"].upper() == "#3B4652"


def test_build_qss_mentions_accent():
    qss = build_qss(TOKENS)
    assert "#0F6CBD" in qss or TOKENS["accent"] in qss
    assert TOKENS["border_strong"] in qss
    assert TOKENS["hover"] in qss
