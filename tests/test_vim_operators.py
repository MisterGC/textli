"""The operator + motion grammar: operators compose with every motion and text
object, and `.` repeats the last change.

The pure landing-place rules live in ``test_vimmotion.py``; this file drives the
handler the way the host does — keystroke in, document and mode out.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QPlainTextEdit  # noqa: E402

from textli.vim import VimKeyHandler, VimMode  # noqa: E402

# Punctuation this suite types. Letters and digits are derived from the char.
_SPECIAL = {
    "$": Qt.Key.Key_Dollar, "^": Qt.Key.Key_AsciiCircum,
    "{": Qt.Key.Key_BraceLeft, "}": Qt.Key.Key_BraceRight,
    "%": Qt.Key.Key_Percent, ".": Qt.Key.Key_Period,
    "~": Qt.Key.Key_AsciiTilde, ";": Qt.Key.Key_Semicolon,
    ",": Qt.Key.Key_Comma, "(": Qt.Key.Key_ParenLeft,
    ")": Qt.Key.Key_ParenRight, "[": Qt.Key.Key_BracketLeft,
    "]": Qt.Key.Key_BracketRight, '"': Qt.Key.Key_QuoteDbl,
    "'": Qt.Key.Key_Apostrophe, " ": Qt.Key.Key_Space,
    "!": Qt.Key.Key_Exclam, "-": Qt.Key.Key_Minus,
}
_ESC = "\x1b"
_BS = "\x08"
_DEL = "\x7f"


def _app():
    return QApplication.instance() or QApplication([])


def _type(text: str, keys: str, pos: int = 0):
    """Run ``keys`` against ``text`` and return ``(document, caret, mode)``.

    An unconsumed key goes to the widget's own handler, which is what the real
    host does — its event filter returns False and Qt delivers the key to the
    ``QPlainTextEdit``. So INSERT-mode typing, Backspace and Delete all behave
    here exactly as they do in the editor.
    """
    _app()
    editor = QPlainTextEdit(text)
    handler = VimKeyHandler(
        editor=editor, mode_changed=lambda m: None,
        close_save=lambda: None, close_cancel=lambda: None)
    cur = editor.textCursor()
    cur.setPosition(pos)
    editor.setTextCursor(cur)
    for ch in keys:
        mods = Qt.KeyboardModifier.NoModifier
        if ch == _ESC:
            key, ch = Qt.Key.Key_Escape, ""
        elif ch == _BS:
            key = Qt.Key.Key_Backspace
        elif ch == _DEL:
            key = Qt.Key.Key_Delete
        elif ch.isalpha():
            key = getattr(Qt.Key, f"Key_{ch.upper()}")
            if ch.isupper():
                mods = Qt.KeyboardModifier.ShiftModifier
        elif ch.isdigit():
            key = getattr(Qt.Key, f"Key_{ch}")
        else:
            key = _SPECIAL[ch]
        event = QKeyEvent(QEvent.Type.KeyPress, key, mods, ch)
        if not handler.handle_key(event):
            QPlainTextEdit.keyPressEvent(editor, event)
    return editor.toPlainText(), editor.textCursor().position(), handler.mode


def _doc(text: str, keys: str, pos: int = 0) -> str:
    return _type(text, keys, pos)[0]


LINE = "foo(bar) baz\n"
PARAS = "first one\nsecond two\nthird three\n\nafter blank\n"


# ── d composes with the motions ──

def test_delete_with_word_motions():
    assert _doc(LINE, "dw") == "(bar) baz\n"
    assert _doc(LINE, "de") == "(bar) baz\n"        # e is inclusive
    assert _doc(LINE, "dW") == "baz\n"              # WORD spans the punctuation
    assert _doc(LINE, "d$") == "\n"
    assert _doc(LINE, "db", 9) == "foo(barbaz\n"


def test_delete_with_line_and_document_motions():
    assert _doc(PARAS, "dj") == "third three\n\nafter blank\n"
    assert _doc(PARAS, "dG") == ""
    assert _doc(PARAS, "dgg", 12) == "third three\n\nafter blank\n"
    assert _doc(PARAS, "d}") == "\nafter blank\n"
    assert _doc("  hello\n", "d^", 5) == "  lo\n"


def test_delete_with_find_motions():
    assert _doc(LINE, "dfr") == ") baz\n"           # f includes the target
    assert _doc(LINE, "dtr") == "r) baz\n"          # t stops before it
    assert _doc(LINE, "dFo", 7) == "fo) baz\n"


def test_delete_with_percent_takes_the_bracketed_run():
    assert _doc("f(a b) x\n", "d%", 1) == "f x\n"


def test_a_failed_find_moves_nothing_and_drops_the_operator():
    # `z` isn't on the line: vim abandons the whole command rather than
    # deleting to some fallback.
    text, pos, mode = _type(LINE, "dfQ")
    assert text == LINE and pos == 0 and mode == VimMode.NORMAL


def test_counts_multiply_across_operator_and_motion():
    assert _doc(LINE, "d2w") == "bar) baz\n"
    assert _doc(LINE, "2d2w") == "baz\n"
    assert _doc(PARAS, "2dd") == "third three\n\nafter blank\n"


# ── c and y ride the same motions ──

def test_change_enters_insert_and_keeps_the_span_out():
    text, _pos, mode = _type(LINE, "ce")
    assert text == "(bar) baz\n" and mode == VimMode.INSERT


def test_cw_behaves_like_ce_and_spares_the_space():
    # vim's one deliberate irregularity: on a non-blank, cw doesn't eat the
    # space the way dw does.
    assert _doc("aaa bbb\n", "cw") == " bbb\n"
    assert _doc("aaa bbb\n", "dw") == "bbb\n"


def test_yank_with_a_motion_then_paste():
    assert _doc("one two\n", "ywP") == "one one two\n"


def test_doubled_operators_are_linewise():
    assert _doc(PARAS, "dd") == "second two\nthird three\n\nafter blank\n"
    text, _pos, mode = _type(PARAS, "cc")
    assert text == "\nsecond two\nthird three\n\nafter blank\n"
    assert mode == VimMode.INSERT           # cc keeps the line, empties it
    assert _doc(PARAS, "yyp") == "first one\nfirst one\nsecond two\nthird three\n\nafter blank\n"


# ── Text objects ──

def test_word_objects():
    assert _doc(LINE, "diw", 5) == "foo() baz\n"
    assert _doc("aaa bbb ccc\n", "daw", 4) == "aaa ccc\n"
    assert _doc(LINE, "diW", 5) == " baz\n"


def test_bracket_objects():
    assert _doc(LINE, "di(", 5) == "foo() baz\n"
    assert _doc(LINE, "da(", 5) == "foo baz\n"
    assert _doc("a [x y] b\n", "di[", 4) == "a [] b\n"
    assert _doc("f{ g }h\n", "da{", 3) == "fh\n"


def test_bracket_object_from_the_bracket_itself_and_when_nested():
    assert _doc("f(a b) x\n", "di(", 1) == "f() x\n"
    assert _doc("f(a (b) c) x\n", "di(", 5) == "f(a () c) x\n"


def test_quote_objects():
    assert _doc('say "hello" ok\n', 'di"', 6) == 'say "" ok\n'
    assert _doc('say "hello" ok\n', 'da"', 6) == "say  ok\n"
    # Found by looking forward from before the opening quote, as vim does.
    assert _doc('say "hello" ok\n', 'di"', 0) == 'say "" ok\n'


def test_paragraph_objects_are_linewise():
    assert _doc(PARAS, "dip") == "\nafter blank\n"
    assert _doc(PARAS, "dap") == "after blank\n"


def test_change_a_text_object_enters_insert():
    text, _pos, mode = _type(LINE, "ci(", 5)
    assert text == "foo() baz\n" and mode == VimMode.INSERT


def test_an_object_with_nothing_under_the_caret_changes_nothing():
    text, _pos, mode = _type("no brackets\n", "di(", 3)
    assert text == "no brackets\n" and mode == VimMode.NORMAL


# ── One-key shorthands ──

def test_shorthand_operators():
    assert _doc(LINE, "D", 3) == "foo\n"
    text, _pos, mode = _type(LINE, "C", 3)
    assert text == "foo\n" and mode == VimMode.INSERT
    assert _doc(PARAS, "Yp") == "first one\nfirst one\nsecond two\nthird three\n\nafter blank\n"
    text, _pos, mode = _type(PARAS, "S")
    assert text.startswith("\nsecond two") and mode == VimMode.INSERT
    text, _pos, mode = _type(LINE, "s")
    assert text == "oo(bar) baz\n" and mode == VimMode.INSERT


def test_x_and_X_stay_on_their_line():
    assert _doc(LINE, "3x") == "(bar) baz\n"
    assert _doc(LINE, "X", 3) == "fo(bar) baz\n"
    # At column 0 there is nothing behind the caret — X must not eat the
    # newline of the line above.
    assert _doc(PARAS, "X", 10) == PARAS
    # Nor may x run past the end of its line.
    assert _doc("ab\ncd\n", "5x") == "\ncd\n"


def test_replace_toggle_case_and_join():
    assert _doc(LINE, "rZ") == "Zoo(bar) baz\n"
    assert _doc(LINE, "3rZ") == "ZZZ(bar) baz\n"
    assert _doc(LINE, "~") == "Foo(bar) baz\n"
    assert _doc("one\n  two\nthree\n", "J") == "one two\nthree\n"
    assert _doc("one\n  two\nthree\n", "3J") == "one two three\n"


# ── `.` repeats the last change ──

def test_dot_repeats_a_delete():
    assert _doc(LINE, "dw.") == "bar) baz\n"
    assert _doc("abcdef\n", "x..") == "def\n"
    assert _doc("l1\nl2\nl3\nl4\n", "dd.") == "l3\nl4\n"


def test_dot_repeats_a_change_including_what_was_typed():
    assert _doc("aaa bbb ccc\n", "cwXY" + _ESC + "0w.") == "XY XY ccc\n"


def test_dot_repeats_an_insert_session():
    assert _doc("one\ntwo\n", "A!" + _ESC + "j.") == "one!\ntwo!\n"


def test_dot_takes_its_own_count():
    assert _doc("abcdefgh\n", "x3.") == "efgh\n"


def test_dot_does_not_repeat_a_motion_or_an_undo():
    # A motion changes nothing, so `.` still repeats the delete before it.
    assert _doc("abcdef\n", "xll.") == "bcef\n"
    # And `.` after an undo repeats the change, never the undo itself: the
    # document ends up shorter, not restored twice over. (Where the caret sits
    # afterwards is Qt's call — its undo returns it to the end of the text it
    # put back, rather than to the start of the change as vim would.)
    assert len(_doc("abcdef\n", "xu.")) == len("abcdef\n") - 1


def test_dot_repeats_a_text_object_change():
    assert _doc("aaa bbb\n", "ciwZ" + _ESC + "w.") == "Z Z\n"


def test_dot_repeats_what_the_insert_leg_left_not_every_key_typed():
    # Backspace and Delete are part of the change. Replaying only the printable
    # keys would put the corrected-away characters back: `iab<BS>c` leaves "ac",
    # so `.` has to leave "ac" too, not "abc".
    assert _doc("one\ntwo\n", "iab" + _BS + "c" + _ESC + "j0.") == "acone\nactwo\n"
    assert _doc("one\ntwo\n", "ia" + _DEL + _ESC + "j0.") == "ane\nawo\n"


# ── VISUAL mode shares the motions and objects ──

def test_visual_takes_text_objects_and_find_motions():
    assert _doc(LINE, "viwd", 5) == "foo() baz\n"
    assert _doc(LINE, "vfrd") == ") baz\n"
    assert _doc(LINE, "vi(d", 5) == "foo() baz\n"


def test_visual_paste_replaces_the_selection():
    assert _doc("word here\n", "yiwwviwp") == "word word\n"


# ── The pending-key contract the host relies on ──

def test_has_pending_covers_the_new_sequences():
    _app()
    editor = QPlainTextEdit(LINE)
    handler = VimKeyHandler(
        editor=editor, mode_changed=lambda m: None,
        close_save=lambda: None, close_cancel=lambda: None)

    def press(key, ch="", mods=Qt.KeyboardModifier.NoModifier):
        handler.handle_key(QKeyEvent(QEvent.Type.KeyPress, key, mods, ch))

    assert not handler.has_pending
    press(Qt.Key.Key_D, "d")                 # operator awaiting a motion
    assert handler.has_pending
    press(Qt.Key.Key_Escape)
    assert not handler.has_pending

    # `f` must hold the next key even when it is one the host would claim —
    # `f/` searches for a slash rather than opening the search overlay.
    press(Qt.Key.Key_F, "f")
    assert handler.has_pending
    press(Qt.Key.Key_R, "r")
    assert not handler.has_pending

    press(Qt.Key.Key_R, "r")                 # r awaits its replacement char
    assert handler.has_pending
    press(Qt.Key.Key_Z, "z")
    assert not handler.has_pending

    press(Qt.Key.Key_2, "2")                 # a count is building
    assert handler.has_pending
    press(Qt.Key.Key_D, "d")
    press(Qt.Key.Key_D, "d")
    assert not handler.has_pending


def test_escape_abandons_a_pending_operator_without_closing():
    closed = []
    _app()
    editor = QPlainTextEdit(LINE)
    handler = VimKeyHandler(
        editor=editor, mode_changed=lambda m: None,
        close_save=lambda: closed.append("save"),
        close_cancel=lambda: closed.append("cancel"))
    handler.handle_key(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_D, Qt.KeyboardModifier.NoModifier, "d"))
    handler.handle_key(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    assert closed == []                      # the Esc went to the operator
    assert editor.toPlainText() == LINE
    handler.handle_key(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    assert closed == ["save"]                # a second Esc closes as before
