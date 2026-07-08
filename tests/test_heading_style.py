"""Read-view heading rhythm: asymmetric margins, rule under h1/h2 (#12)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.editor import ZenMarkdownEditor  # noqa: E402

MD = ("# Top Title\n\nintro prose\n\n"
      "## Section One\n\nbody text\n\n"
      "### Detail\n\nmore body\n")


def _editor(md: str = MD) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, md, title="T")
    ed._parent = parent
    return ed


def _headings(doc):
    out = {}
    block = doc.begin()
    while block.isValid():
        level = block.blockFormat().headingLevel()
        if level:
            out[level] = block
        block = block.next()
    return out


def test_heading_margins_are_asymmetric_more_above_than_below():
    ed = _editor()
    ed._toggle_rendered()
    hs = _headings(ed._rendered.document())
    for level in (1, 2, 3):
        bf = hs[level].blockFormat()
        assert bf.topMargin() > bf.bottomMargin() > 0


def test_heading_margins_scale_down_with_level():
    ed = _editor()
    ed._toggle_rendered()
    hs = _headings(ed._rendered.document())
    tops = {lv: hs[lv].blockFormat().topMargin() for lv in (1, 2, 3)}
    assert tops[1] > tops[2] > tops[3]


def test_rules_mark_h1_and_h2_but_not_h3():
    ed = _editor()
    ed._toggle_rendered()
    hs = _headings(ed._rendered.document())
    rules = ed._rendered._heading_rules
    assert hs[1].position() in rules
    assert hs[2].position() in rules
    assert hs[3].position() not in rules
    assert len(rules) == 2


def test_clean_preview_keeps_the_heading_treatment():
    ed = _editor()
    ed._toggle_rendered()
    ed._toggle_preview()
    hs = _headings(ed._rendered.document())
    assert hs[2].blockFormat().topMargin() > hs[2].blockFormat().bottomMargin()
    assert len(ed._rendered._heading_rules) == 2


def test_heading_margins_scale_with_font_zoom():
    ed = _editor()
    ed._toggle_rendered()
    top_before = _headings(
        ed._rendered.document())[2].blockFormat().topMargin()
    for _ in range(4):
        ed._change_font_size(+1)
    top_after = _headings(
        ed._rendered.document())[2].blockFormat().topMargin()
    assert top_after > top_before
