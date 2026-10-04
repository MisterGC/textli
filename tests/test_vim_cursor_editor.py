"""Where the caret rests in the full editor (#78): `Esc` never leaves its line,
`$` and `l` stop on the last character, `cw` changes only the word it is in,
and a count followed by `Esc` drops the count instead of closing.

Driven through ``ZenMarkdownEditor`` rather than ``VimKeyHandler`` alone: keys
go to the write view as events, so the editor's filter sees them first — the
same path on which a bare `Esc` saves and closes."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.editor import ZenMarkdownEditor  # noqa: E402
from textli.vim import VimMode  # noqa: E402

_KEYS = {"$": Qt.Key.Key_Dollar, "\x1b": Qt.Key.Key_Escape}


def _editor(text, tmp_path, pos=0) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    path = Path(tmp_path) / "doc.md"
    path.write_text(text, encoding="utf-8")
    ed = ZenMarkdownEditor(parent, text, title="T", file_path=path)
    ed._parent = parent
    if ed._rendered_mode:
        ed._toggle_rendered()
    # Record a close instead of running it, so a test can tell `Esc` closing
    # from `Esc` being consumed.
    ed.closes = []
    ed._request_close = lambda *, cancel=False: ed.closes.append(cancel)
    cur = ed._editor.textCursor()
    cur.setPosition(pos)
    ed._editor.setTextCursor(cur)
    return ed


def _type(ed, keys):
    """Send each character as a key event; `\\x1b` is Esc."""
    for ch in keys:
        if ch in _KEYS:
            key = _KEYS[ch]
        elif ch.isalpha():
            key = getattr(Qt.Key, f"Key_{ch.upper()}")
        else:
            key = getattr(Qt.Key, f"Key_{ch}")
        mods = (Qt.KeyboardModifier.ShiftModifier if ch.isupper()
                else Qt.KeyboardModifier.NoModifier)
        text = "" if ch == "\x1b" else ch
        QApplication.sendEvent(ed._editor, QKeyEvent(
            QEvent.Type.KeyPress, key, mods, text))


def _pos(ed):
    return ed._editor.textCursor().position()


def test_i_then_esc_at_column_0_stays_on_its_line(tmp_path):
    ed = _editor("one\ntwo\n", tmp_path, pos=4)
    _type(ed, "i\x1b")
    assert ed._vim.mode == VimMode.NORMAL
    assert _pos(ed) == 4
    assert ed.closes == []


def test_o_then_esc_stays_on_the_opened_line(tmp_path):
    ed = _editor("one\ntwo", tmp_path, pos=0)
    _type(ed, "o\x1b")
    assert ed._editor.toPlainText() == "one\n\ntwo"
    assert _pos(ed) == 4
    assert ed._editor.textCursor().blockNumber() == 1


def test_esc_after_typing_steps_back_onto_the_typed_character(tmp_path):
    ed = _editor("one\n", tmp_path, pos=0)
    _type(ed, "ix\x1b")
    assert ed._editor.toPlainText() == "xone\n"
    assert _pos(ed) == 0


def test_dollar_rests_on_the_last_character_and_x_deletes_it(tmp_path):
    ed = _editor("abc\ndef\n", tmp_path, pos=0)
    _type(ed, "$")
    assert _pos(ed) == 2
    _type(ed, "x")
    assert ed._editor.toPlainText() == "ab\ndef\n"
    # The caret moves onto the new last character, not past the line.
    assert _pos(ed) == 1


def test_l_never_goes_past_the_last_character(tmp_path):
    ed = _editor("abc\ndef\n", tmp_path, pos=0)
    _type(ed, "lllll")
    assert _pos(ed) == 2
    _type(ed, "$l")
    assert _pos(ed) == 2


def test_d_dollar_and_dl_still_take_the_last_character(tmp_path):
    ed = _editor("abc\n", tmp_path, pos=1)
    _type(ed, "d$")
    assert ed._editor.toPlainText() == "a\n"
    ed = _editor("abc\n", tmp_path, pos=2)
    _type(ed, "dl")
    assert ed._editor.toPlainText() == "ab\n"


def test_visual_dollar_still_selects_the_last_character(tmp_path):
    ed = _editor("abc\n", tmp_path, pos=0)
    _type(ed, "v$d")
    assert ed._editor.toPlainText() == "\n"


def test_cw_on_a_one_letter_word_changes_only_that_word(tmp_path):
    ed = _editor("a b", tmp_path, pos=0)
    _type(ed, "cwX\x1b")
    assert ed._editor.toPlainText() == "X b"


def test_cw_on_a_words_last_character_changes_only_that_character(tmp_path):
    ed = _editor("ab cd", tmp_path, pos=1)
    _type(ed, "cwX\x1b")
    assert ed._editor.toPlainText() == "aX cd"


def test_cw_mid_word_still_changes_to_the_words_end(tmp_path):
    ed = _editor("abc def", tmp_path, pos=1)
    _type(ed, "cwX\x1b")
    assert ed._editor.toPlainText() == "aX def"


def test_count_then_esc_drops_the_count_and_does_not_close(tmp_path):
    ed = _editor("abcdef\n", tmp_path, pos=0)
    _type(ed, "3\x1b")
    assert ed.closes == []
    assert not ed._vim.has_pending
    # The count is gone: `x` now deletes one character, not three.
    _type(ed, "x")
    assert ed._editor.toPlainText() == "bcdef\n"


def test_bare_esc_in_normal_still_closes(tmp_path):
    ed = _editor("abc\n", tmp_path, pos=0)
    _type(ed, "\x1b")
    assert ed.closes == [False]
