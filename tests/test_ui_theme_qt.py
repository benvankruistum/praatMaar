from ui.theme import TOKENS, build_qss


def test_tokens_include_canvas_accent():
    assert TOKENS["accent"].upper() == "#0F6CBD"


def test_build_qss_mentions_accent():
    qss = build_qss(TOKENS)
    assert "#0F6CBD" in qss or TOKENS["accent"] in qss
