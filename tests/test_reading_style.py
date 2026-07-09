"""Inline-code chips, blockquote voice (#13), read-view section focus (#14)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.constants import (  # noqa: E402
    ZEN_HINT_COLOR,
    ZEN_MD_CODE_BLOCK_BG,
)
from textli.editor import ZenMarkdownEditor  # noqa: E402

MD = ("# One\n\n"
      "Prose with `inline_code` in it.\n\n"
      "> a quote line\n> continued quote\n\n"
      "Plain prose after.\n\n"
      "```python\nx = 1\n```\n\n"
      "# Two\n\nSecond section prose.\n\n"
      "# Three\n\nThird section prose.\n")


def _editor(md: str = MD) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, md, title="T")
    ed._parent = parent
    return ed


def _fragments(doc):
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            yield block, it.fragment()
            it += 1
        block = block.next()


# ── inline-code chips ──

def test_inline_code_gets_the_chip_wash():
    ed = _editor()
    ed._toggle_rendered()
    frags = {f.text(): f for _b, f in _fragments(ed._rendered.document())}
    chip = frags["inline_code"].charFormat()
    assert chip.background().color().name() == ZEN_MD_CODE_BLOCK_BG.name()


def test_fenced_code_keeps_no_char_background():
    # the fence has the painted band; chips must not double-wash it
    ed = _editor()
    ed._toggle_rendered()
    from PySide6.QtCore import Qt
    for block, frag in _fragments(ed._rendered.document()):
        if block.text() == "x = 1":
            assert (frag.charFormat().background().style()
                    == Qt.BrushStyle.NoBrush)


def test_chips_survive_the_clean_preview():
    ed = _editor()
    ed._toggle_rendered()
    ed._toggle_preview()
    frags = {f.text(): f for _b, f in _fragments(ed._rendered.document())}
    assert (frags["inline_code"].charFormat().background().color().name()
            == ZEN_MD_CODE_BLOCK_BG.name())


# ── blockquotes ──

def test_quotes_wear_hint_ink_and_register_a_bar():
    ed = _editor()
    ed._toggle_rendered()
    doc = ed._rendered.document()
    quote_block = None
    block = doc.begin()
    while block.isValid():
        if "a quote line" in block.text():
            quote_block = block
            break
        block = block.next()
    assert quote_block is not None
    it = quote_block.begin()
    frag = it.fragment()
    assert (frag.charFormat().foreground().color().name()
            == ZEN_HINT_COLOR.name())
    assert ed._rendered._quote_bars == [
        (quote_block.position(), quote_block.position())]


def test_prose_keeps_body_ink():
    ed = _editor()
    ed._toggle_rendered()
    for block, frag in _fragments(ed._rendered.document()):
        if "Plain prose after." in frag.text():
            assert (frag.charFormat().foreground().color().name()
                    != ZEN_HINT_COLOR.name())


# ── read-view section focus ──

def _caret_to(ed, needle: str):
    pos = ed._rendered.toPlainText().index(needle)
    cur = ed._rendered.textCursor()
    cur.setPosition(pos)
    ed._rendered.setTextCursor(cur)


def test_focus_off_means_no_wash():
    ed = _editor()
    ed._toggle_rendered()
    assert ed._rendered._focus_span is None


def test_focus_covers_the_section_under_the_caret():
    ed = _editor()
    ed._focus_enabled = True
    ed._toggle_rendered()
    _caret_to(ed, "Second section prose")
    span = ed._rendered._focus_span
    assert span is not None
    text = ed._rendered.toPlainText()
    start, end = span
    assert start <= text.index("Two")
    assert end >= text.index("Second section prose")
    assert end < text.index("Three")


def test_focus_follows_the_caret_between_sections():
    ed = _editor()
    ed._focus_enabled = True
    ed._toggle_rendered()
    _caret_to(ed, "Second section prose")
    span_two = ed._rendered._focus_span
    _caret_to(ed, "Third section prose")
    span_three = ed._rendered._focus_span
    assert span_three != span_two
    assert span_three[1] > span_two[1]


def test_toggle_focus_in_read_view_sets_and_lifts_the_wash():
    ed = _editor()
    ed._toggle_rendered()
    assert ed._rendered._focus_span is None
    ed._toggle_focus()
    assert ed._rendered._focus_span is not None
    ed._toggle_focus()
    assert ed._rendered._focus_span is None


def test_leaving_read_mode_lifts_the_wash():
    ed = _editor()
    ed._focus_enabled = True
    ed._toggle_rendered()
    _caret_to(ed, "Second section prose")
    assert ed._rendered._focus_span is not None
    ed._toggle_rendered()   # back to write
    assert ed._rendered._focus_span is None


# ── Read-view block caret (visible on the warm page for comment placement) ──

def test_read_view_hides_the_native_thin_caret():
    ed = _editor()
    ed._toggle_rendered()
    # width 0 hides Qt's 1px line; the view paints its own soft block instead
    assert ed._rendered.cursorWidth() == 0


def _lay_out(v):
    """Give the headless view a real layout so line geometry exists."""
    v.setFixedSize(800, 600)
    v.document().setTextWidth(v.viewport().width())


def test_caret_cell_covers_the_current_glyph():
    from PySide6.QtCore import QPointF
    ed = _editor()
    ed._toggle_rendered()
    v = ed._rendered
    _lay_out(v)
    idx = v.toPlainText().index("Prose")
    cur = v.textCursor()
    cur.setPosition(idx)
    v.setTextCursor(cur)
    cell = v._caret_cell(QPointF(0, 0))
    assert cell is not None
    assert cell.width() > 0 and cell.height() > 0


def test_caret_cell_handles_end_of_block():
    # at a block end there is no next glyph — falls back to a space width,
    # never raising
    from PySide6.QtCore import QPointF
    ed = _editor()
    ed._toggle_rendered()
    v = ed._rendered
    _lay_out(v)
    block = v.document().begin()
    cur = v.textCursor()
    cur.setPosition(block.position() + max(0, block.length() - 1))
    v.setTextCursor(cur)
    cell = v._caret_cell(QPointF(0, 0))
    assert cell is not None and cell.width() > 0
