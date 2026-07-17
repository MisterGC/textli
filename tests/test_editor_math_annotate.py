"""Annotating math in the read view: a formula renders as a single image
(a word-less object-replacement char), so the read-view selection→source
mapping is given formula anchors — letting `c` / `s` land on a formula the
same as on prose. See issue #36 (math support)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextCursor  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.constants import ZEN_MD_COMMENT_HL  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402

OBJ = "￼"   # object-replacement char — how a rendered image reads as text

MD = (
    "The relation $E = mc^2$ holds in general.\n\n"
    "A display line:\n\n"
    "$$a^2 + b^2 = c^2$$\n"
)


def _editor(text: str = MD) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, text, title="T")
    ed._parent = parent            # keep a ref alive
    ed._suggest_animate = False     # deterministic — no tween
    ed._toggle_rendered()
    return ed


def _select(ed, r0: int, r1: int):
    cur = ed._rendered.textCursor()
    cur.setPosition(r0)
    cur.setPosition(r1, QTextCursor.MoveMode.KeepAnchor)
    ed._rendered.setTextCursor(cur)


def _put_caret(ed, pos: int):
    cur = ed._rendered.textCursor()
    cur.setPosition(pos)
    ed._rendered.setTextCursor(cur)


def test_anchors_pair_each_formula_image_with_its_source_span():
    ed = _editor()
    rendered = ed._rendered.document().toPlainText()
    src = ed._editor.toPlainText()
    # one anchor per formula, in document order
    assert len(ed._rendered_math) == 2
    for rpos, s0, s1 in ed._rendered_math:
        assert rendered[rpos] == OBJ            # points at the image glyph
        assert src[s0] == "$" and src[s1 - 1] == "$"   # a $…$ / $$…$$ span
    # inline first, display second
    assert "E = mc^2" in src[slice(*ed._rendered_math[0][1:])]
    assert "a^2 + b^2 = c^2" in src[slice(*ed._rendered_math[1][1:])]


def test_comment_a_formula_via_caret_gesture():
    # Caret sits on the inline formula image; `c` with no selection authors a
    # comment on it (no visual-select needed for a one-char image).
    ed = _editor()
    _put_caret(ed, ed._rendered_math[0][0])
    ed._comment_selection()
    assert ed._comment_field is not None            # authoring opened
    ed._comment_field.setPlainText("right form?")
    ed._commit_comment_field()
    src = ed._editor.toPlainText()
    assert "{==$E = mc^2$==}{>>right form?<<}" in src
    assert len(ed._rendered_comments) == 1


def test_comment_a_formula_via_visual_selection():
    ed = _editor()
    fpos = ed._rendered_math[0][0]
    _select(ed, fpos, fpos + 1)
    ed._comment_selection()
    assert ed._comment_field is not None
    ed._comment_field.setPlainText("note")
    ed._commit_comment_field()
    assert "{==$E = mc^2$==}{>>note<<}" in ed._editor.toPlainText()


def test_commented_formula_still_renders_highlighted():
    ed = _editor()
    _put_caret(ed, ed._rendered_math[0][0])
    ed._comment_selection()
    ed._comment_field.setPlainText("q")
    ed._commit_comment_field()
    # after the re-render the formula is still an image, now under the wash
    doc = ed._rendered.document()
    rendered = doc.toPlainText()
    fpos = rendered.index(OBJ)
    cur = ed._rendered.textCursor()
    cur.setPosition(fpos)
    cur.setPosition(fpos + 1, QTextCursor.MoveMode.KeepAnchor)
    fmt = cur.charFormat()
    assert fmt.isImageFormat()
    assert fmt.background().color() == ZEN_MD_COMMENT_HL


def test_suggest_a_replacement_on_a_formula():
    ed = _editor()
    fpos = ed._rendered_math[1][0]                   # the display formula
    _select(ed, fpos, fpos + 1)
    ed._begin_suggestion_for_span(fpos, fpos + 1)
    assert ed._comment_field is not None
    ed._comment_field.setPlainText("$$a^2 + b^2 = c^2 = d$$")
    ed._commit_new_suggestion(ed._comment_field.toPlainText())
    src = ed._editor.toPlainText()
    assert "{~~$$a^2 + b^2 = c^2$$~>$$a^2 + b^2 = c^2 = d$$~~}" in src
    assert len(ed._rendered_suggestions) == 1


def test_range_spanning_a_formula_wraps_the_whole_range():
    # Pre-existing behavior must survive: a prose+formula selection wraps the
    # lot, formula source included.
    ed = _editor()
    rendered = ed._rendered.document().toPlainText()
    r0 = rendered.index("relation")
    r1 = rendered.index("holds") + len("holds")
    _select(ed, r0, r1)
    ed._comment_selection()
    ed._comment_field.setPlainText("whole clause")
    ed._commit_comment_field()
    src = ed._editor.toPlainText()
    assert "{==relation $E = mc^2$ holds==}{>>whole clause<<}" in src


def test_bare_caret_off_any_formula_does_not_author():
    # `c` on ordinary prose with no selection still just tries to reveal a
    # comment under the caret — it must not spuriously author on non-formulas.
    ed = _editor()
    rendered = ed._rendered.document().toPlainText()
    _put_caret(ed, rendered.index("general"))
    ed._comment_selection()
    assert ed._comment_field is None
    assert ed._editor.toPlainText() == MD
