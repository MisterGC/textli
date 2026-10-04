"""Callout/admonition boxes in the reading view (#35).

Two halves, matching the split in the code: the marker grammar over a plain
string (`callouts.py`), and what the reading view makes of it — a labelled
block on a tinted box, with a plain blockquote left exactly as it was.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QTextFormat  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli import callouts, theme  # noqa: E402
from textli.editor import _CALLOUT_KIND_PROP, ZenMarkdownEditor  # noqa: E402

PLAIN_QUOTE = "> a plain quote\n> continued\n"


def _editor(md: str) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, md, title="T")
    ed._parent = parent
    ed._toggle_rendered()
    return ed


def _blocks(doc):
    block = doc.begin()
    while block.isValid():
        yield block
        block = block.next()


def _quoted(doc):
    """Every blockquote block of the rendered document, in order."""
    return [b for b in _blocks(doc)
            if b.blockFormat().intProperty(
                QTextFormat.Property.BlockQuoteLevel) > 0]


# ── the marker grammar (Qt-free) ──

def test_the_five_github_kinds_are_recognised():
    for kind in ("NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"):
        found = callouts.match(f"[!{kind}] body text")
        assert found is not None and found.kind == kind
        # the marker *and* the blank after it belong to the label's span
        assert f"[!{kind}] body text"[found.end:] == "body text"


def test_the_kind_is_matched_case_insensitively_but_canonicalised():
    found = callouts.match("[!note] body")
    assert found is not None and found.kind == "NOTE"


def test_an_unknown_kind_and_a_late_marker_are_not_callouts():
    assert callouts.match("[!BOGUS] body") is None
    assert callouts.match("see [!NOTE] over there") is None
    assert callouts.match("a plain quote") is None


def test_a_marker_alone_on_the_line_ends_at_the_line_end():
    found = callouts.match("[!WARNING]")
    assert found is not None and found.end == len("[!WARNING]")


# ── the rendered box ──

def _plain_quote_format():
    """The block format a plain blockquote renders with — the baseline the
    'unchanged' assertions below are measured against."""
    ed = _editor(PLAIN_QUOTE)
    return _quoted(ed._rendered.document())[0].blockFormat()


def test_each_kind_renders_a_labelled_block_tinted_off_a_plain_quote():
    plain_bg = _plain_quote_format().background()
    for kind in callouts.KINDS:
        ed = _editor(f"> [!{kind}]\n> the body of the callout\n")
        quoted = _quoted(ed._rendered.document())
        # the label is split out onto a block of its own, the body follows
        assert [b.text() for b in quoted] == [kind, "the body of the callout"]
        for block in quoted:
            bf = block.blockFormat()
            assert bf.stringProperty(_CALLOUT_KIND_PROP) == kind
            assert bf.background() != plain_bg
            assert (bf.background().color().name()
                    == theme.callout_fill(kind).name())


def test_the_label_wears_its_kind_accent_bold():
    ed = _editor("> [!CAUTION]\n> mind the gap\n")
    label = _quoted(ed._rendered.document())[0]
    fmt = label.begin().fragment().charFormat()
    assert (fmt.foreground().color().name()
            == theme.callout_accent("CAUTION").name())
    assert fmt.fontWeight() == QFont.Weight.Bold.value


def test_each_kind_gets_its_own_accent():
    accents = {k: theme.callout_accent(k).name() for k in callouts.KINDS}
    assert len(set(accents.values())) == len(callouts.KINDS)


def test_the_bar_moves_from_the_quote_list_to_the_callout_list():
    ed = _editor("> [!TIP]\n> try this\n")
    label = _quoted(ed._rendered.document())[0]
    assert ed._rendered._quote_bars == []
    assert len(ed._rendered._callout_bars) == 1
    first, _last, colour = ed._rendered._callout_bars[0]
    assert first == label.position()
    assert colour.name() == theme.callout_accent("TIP").name()


def test_a_plain_blockquote_renders_unchanged():
    ed = _editor(PLAIN_QUOTE)
    quoted = _quoted(ed._rendered.document())
    assert [b.text() for b in quoted] == ["a plain quote continued"]
    bf = quoted[0].blockFormat()
    assert not bf.hasProperty(_CALLOUT_KIND_PROP)
    assert bf.background().style().name == "NoBrush"
    assert ed._rendered._callout_bars == []
    assert ed._rendered._quote_bars == [
        (quoted[0].position(), quoted[0].position())]


def test_an_unknown_kind_falls_back_to_a_plain_blockquote():
    ed = _editor("> [!BOGUS]\n> body\n")
    quoted = _quoted(ed._rendered.document())
    # marker untouched, one block, no tint, an ordinary quote bar
    assert [b.text() for b in quoted] == ["[!BOGUS] body"]
    bf = quoted[0].blockFormat()
    assert not bf.hasProperty(_CALLOUT_KIND_PROP)
    assert bf.background().style().name == "NoBrush"
    assert ed._rendered._callout_bars == []
    assert ed._rendered._quote_bars == [
        (quoted[0].position(), quoted[0].position())]


def test_a_callout_and_a_plain_quote_coexist_in_one_document():
    ed = _editor(f"> [!NOTE]\n> noted\n\nProse.\n\n{PLAIN_QUOTE}")
    quoted = _quoted(ed._rendered.document())
    assert [b.text() for b in quoted] == [
        "NOTE", "noted", "a plain quote continued"]
    assert len(ed._rendered._callout_bars) == 1
    assert len(ed._rendered._quote_bars) == 1


def test_a_marker_alone_in_its_quote_opens_no_empty_line():
    ed = _editor("> [!NOTE]\n")
    quoted = _quoted(ed._rendered.document())
    assert [b.text() for b in quoted] == ["NOTE"]


def test_the_tint_follows_a_theme_switch():
    before = theme.callout_fill("WARNING").name()
    theme.set_theme("dark")
    try:
        assert theme.callout_fill("WARNING").name() != before
        ed = _editor("> [!WARNING]\n> careful\n")
        bf = _quoted(ed._rendered.document())[0].blockFormat()
        assert (bf.background().color().name()
                == theme.callout_fill("WARNING").name())
    finally:
        theme.set_theme("light")
