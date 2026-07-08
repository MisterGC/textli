"""Code blocks in the read view: band + calm zen token colors (#11)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextFormat  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.codeblocks import highlight_spans  # noqa: E402
from textli.constants import (  # noqa: E402
    ZEN_CODE_COMMENT,
    ZEN_CODE_KEYWORD,
    ZEN_CODE_NUMBER,
    ZEN_CODE_STRING,
    ZEN_MD_CODE_BLOCK_BG,
)
from textli.editor import ZenMarkdownEditor  # noqa: E402

CODE_MD = ("# Doc\n\n"
           "Some prose first.\n\n"
           "```python\n"
           "def f(x):\n"
           "    return \"hi\"  # note\n"
           "```\n\n"
           "```\n"
           "plain fence, no language\n"
           "```\n\n"
           "Prose after.\n")


# ── highlight_spans: pure logic ──

def test_spans_classify_the_four_zen_classes():
    code = 'def f(x):\n    return "hi"  # note\n\ncount = 42'
    got = {(code[s:e], cls) for s, e, cls in highlight_spans(code, "python")}
    assert ("def", "keyword") in got
    assert ("return", "keyword") in got
    assert ("hi", "string") in got
    assert ("# note", "comment") in got
    assert ("42", "number") in got


def test_spans_cover_multiline_strings_as_one_unit():
    code = 's = """first\nsecond"""'
    spans = highlight_spans(code, "python")
    string_text = "".join(code[s:e] for s, e, c in spans if c == "string")
    assert "first" in string_text and "second" in string_text


def test_keyword_constants_wear_the_constant_class():
    spans = highlight_spans("x = True", "python")
    got = {("x = True"[s:e], cls) for s, e, cls in spans}
    assert ("True", "number") in got


def test_unknown_or_empty_language_yields_no_spans():
    assert highlight_spans("def f(): pass", "nosuchlanguage") == []
    assert highlight_spans("def f(): pass", "") == []


# ── Rendered view integration ──

def _editor(md: str = CODE_MD) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, md, title="T")
    ed._parent = parent
    return ed


def _code_blocks(doc):
    out = []
    block = doc.begin()
    while block.isValid():
        if block.blockFormat().hasProperty(
                QTextFormat.Property.BlockCodeFence):
            out.append(block)
        block = block.next()
    return out


def _fg_by_text(doc):
    """Map fragment text -> foreground color name, code blocks only."""
    got = {}
    for block in _code_blocks(doc):
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            got[frag.text()] = frag.charFormat().foreground().color().name()
            it += 1
    return got


def test_every_fenced_block_sits_on_the_band():
    ed = _editor()
    ed._toggle_rendered()
    blocks = _code_blocks(ed._rendered.document())
    assert len(blocks) >= 3   # two python lines + one plain line
    for b in blocks:
        bg = b.blockFormat().background().color()
        assert bg.name() == ZEN_MD_CODE_BLOCK_BG.name()


def test_python_fence_wears_the_zen_token_colors():
    ed = _editor()
    ed._toggle_rendered()
    fg = _fg_by_text(ed._rendered.document())

    def color_of(needle):
        # adjacent same-format ranges merge into one fragment ("hi" keeps
        # its quotes), so look the text up by containment
        return next(c for t, c in fg.items() if needle in t)

    assert color_of("def") == ZEN_CODE_KEYWORD.name()
    assert color_of("return") == ZEN_CODE_KEYWORD.name()
    assert color_of("hi") == ZEN_CODE_STRING.name()
    assert color_of("# note") == ZEN_CODE_COMMENT.name()


def test_plain_fence_gets_band_but_stays_ink():
    ed = _editor()
    ed._toggle_rendered()
    fg = _fg_by_text(ed._rendered.document())
    zen = {ZEN_CODE_KEYWORD.name(), ZEN_CODE_STRING.name(),
           ZEN_CODE_COMMENT.name(), ZEN_CODE_NUMBER.name()}
    for text, color in fg.items():
        if "plain fence" in text:
            assert color not in zen


def test_clean_preview_styles_code_blocks_too():
    ed = _editor()
    ed._toggle_rendered()
    ed._toggle_preview()
    fg = _fg_by_text(ed._rendered.document())
    assert fg.get("def") == ZEN_CODE_KEYWORD.name()


def test_adjacent_fences_with_different_languages_stay_separate():
    md = ("```python\nimport os\n```\n"
          "```text\nimport os\n```\n")
    ed = _editor(md)
    ed._toggle_rendered()
    fg = _fg_by_text(ed._rendered.document())
    # both lines say "import os"; only the python one may wear keyword blue —
    # the mapping keys by text, so equal texts colliding is fine: the test
    # is that no crash occurs and blocks got the band.
    blocks = _code_blocks(ed._rendered.document())
    assert len(blocks) == 2
    for b in blocks:
        assert (b.blockFormat().background().color().name()
                == ZEN_MD_CODE_BLOCK_BG.name())


def test_multiline_string_across_blank_line_stays_one_string():
    # blank lines inside a fence keep the BlockCodeFence property, so the
    # whole fence lexes as one unit and the triple-quoted string holds.
    md = "```python\nb = '''first\n\nsecond'''\n```\n"
    ed = _editor(md)
    ed._toggle_rendered()
    fg = _fg_by_text(ed._rendered.document())
    reds = [t for t, c in fg.items() if c == ZEN_CODE_STRING.name()]
    joined = " ".join(reds)
    assert "first" in joined and "second" in joined
