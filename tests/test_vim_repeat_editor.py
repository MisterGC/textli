"""`.` in the full editor (#71): it repeats the last *vim* change — textli's
own document edits (a comment from the reading view, `gs`) never become the
change to repeat — and an arrow key typed mid-insert stays part of it.

Driven through ``ZenMarkdownEditor`` rather than ``VimKeyHandler`` alone: keys
go to the write view as events, so the editor's filter sees them first and an
arrow the handler leaves alone falls through to the widget, as it does live."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QTextCursor  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli import comments as md_comments  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402

DOC = ("---\nstatus: draft\nstatuses: draft, review\n---\n\n"
       "abcdef\n\nthe quick brown fox\n")

_ESC = "\x1b"
_LEFT = "\x02"
_RIGHT = "\x06"
_SPECIAL = {_ESC: Qt.Key.Key_Escape, _LEFT: Qt.Key.Key_Left,
            _RIGHT: Qt.Key.Key_Right, ".": Qt.Key.Key_Period}


def _editor(text, tmp_path) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    path = Path(tmp_path) / "doc.md"
    path.write_text(text, encoding="utf-8")
    ed = ZenMarkdownEditor(parent, text, title="T", file_path=path)
    ed._parent = parent
    if ed._rendered_mode:
        ed._toggle_rendered()
    return ed


def _caret_to(ed, needle: str):
    cur = ed._editor.textCursor()
    cur.setPosition(ed._editor.toPlainText().index(needle))
    ed._editor.setTextCursor(cur)


def _write_keys(ed, keys: str):
    """Send ``keys`` to the write view as real key events."""
    for ch in keys:
        if ch in _SPECIAL:
            key, text = _SPECIAL[ch], ("" if ch in (_ESC, _LEFT, _RIGHT) else ch)
        else:
            key, text = getattr(Qt.Key, f"Key_{ch.upper()}"), ch
        QApplication.sendEvent(ed._editor, QKeyEvent(
            QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, text))


def _read_key(ed, key, text=""):
    ed._handle_rendered_key(QKeyEvent(
        QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, text))


def _comment_from_reading_view(ed, span: str, body: str):
    rendered = ed._rendered.document().toPlainText()
    r0 = rendered.index(span)
    ed._begin_comment_for_span(r0, r0 + len(span))
    ed._comment_field.setPlainText(body)
    ed._commit_comment_field()


# ── `.` repeats the last vim change, never a host edit ──

def test_dot_repeats_the_vim_change_not_a_comment_or_gs(tmp_path):
    ed = _editor(DOC, tmp_path)
    _caret_to(ed, "abcdef")
    _write_keys(ed, "x")
    assert "bcdef\n" in ed._editor.toPlainText()

    # Two host edits from the reading view, each changing the source.
    ed._toggle_rendered()
    _comment_from_reading_view(ed, "quick", "why?")
    _read_key(ed, Qt.Key.Key_G, "g")
    _read_key(ed, Qt.Key.Key_S, "s")
    _read_key(ed, Qt.Key.Key_J, "j")
    _read_key(ed, Qt.Key.Key_Return)
    src = ed._editor.toPlainText()
    assert "status: review" in src
    assert [c.span for c in md_comments.parse(src)] == ["quick"]

    # Back in the write view, `.` deletes one more char — the `x` — and
    # leaves the comment and the status as they are.
    ed._toggle_rendered()
    _caret_to(ed, "bcdef")
    _write_keys(ed, ".")
    after = ed._editor.toPlainText()
    assert after == src.replace("bcdef", "cdef", 1)
    assert after.count("{>>") == 1
    assert "status: review" in after


# ── An arrow key mid-insert stays part of the repeat ──

def test_an_arrow_mid_insert_is_repeated_with_the_rest_of_the_leg(tmp_path):
    # Vim would split the change at the arrow, so `.` would put in only "X";
    # textli repeats the whole leg, the arrow replayed as a caret move.
    ed = _editor("one\ntwo\n", tmp_path)
    _caret_to(ed, "one")
    _write_keys(ed, "iab" + _LEFT + "X" + _ESC)
    assert ed._editor.toPlainText() == "aXbone\ntwo\n"
    _caret_to(ed, "two")
    _write_keys(ed, ".")
    assert ed._editor.toPlainText() == "aXbone\naXbtwo\n"


def test_a_right_arrow_out_of_the_typed_text_is_repeated_too(tmp_path):
    ed = _editor("one\ntwo\n", tmp_path)
    _caret_to(ed, "one")
    _write_keys(ed, "iA" + _RIGHT + "B" + _ESC)
    assert ed._editor.toPlainText() == "AoBne\ntwo\n"
    _caret_to(ed, "two")
    _write_keys(ed, ".")
    assert ed._editor.toPlainText() == "AoBne\nAtBwo\n"
