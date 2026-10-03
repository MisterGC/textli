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
    ">": Qt.Key.Key_Greater, "<": Qt.Key.Key_Less,
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


# ── > and < shift lines; gu, gU and g~ change case ──

def test_shift_operators_indent_and_outdent_whole_lines():
    text, pos, _mode = _type("one\ntwo\n", ">>", 2)
    assert text == "    one\ntwo\n"
    assert pos == 4                          # on the first non-blank
    assert _doc("    one\ntwo\n", "<<") == "one\ntwo\n"
    assert _doc("a\nb\nc\nd\n", "3>>") == "    a\n    b\n    c\nd\n"
    assert _doc("a\nb\nc\nd\n", ">j") == "    a\n    b\nc\nd\n"
    # A motion within the line still shifts the whole line.
    assert _doc("one two\n", ">w") == "    one two\n"


def test_shift_takes_a_text_object_and_skips_blank_lines():
    assert _doc("a\nb\n\nc\n", ">ip", 2) == "    a\n    b\n\nc\n"
    assert _doc("a\n\nb\n", ">2j") == "    a\n\n    b\n"


def test_outdent_stops_at_column_zero_and_reads_a_tab_as_four_columns():
    assert _doc("  a\n", "<<") == "a\n"
    assert _doc("\ta\n", "<<") == "a\n"
    assert _doc("\t  a\n", "<<") == "  a\n"
    assert _doc("a\n", "<<") == "a\n"


def test_shift_repeats_with_dot_and_leaves_the_register_alone():
    assert _doc("a\n", ">>.") == "        a\n"
    assert _doc("a\nb\n", "yy>>jp") == "    a\nb\na\n"


def test_case_operators_take_motions_and_text_objects():
    text, pos, _mode = _type("hello world\n", "gUiw", 2)
    assert text == "HELLO world\n" and pos == 0
    assert _doc("HELLO World\n", "guw") == "hello World\n"
    assert _doc("Hello World\n", "g~w") == "hELLO World\n"
    assert _doc("one two\n", "gU$") == "ONE TWO\n"
    assert _doc("one two\n", "gUe", 4) == "one TWO\n"


def test_case_operators_take_counts():
    assert _doc("one two three\n", "gU2w") == "ONE TWO three\n"
    assert _doc("one two three\n", "2gUw") == "ONE TWO three\n"
    assert _doc("ab\ncd\nef\n", "2gUU") == "AB\nCD\nef\n"


def test_doubled_case_operators_take_the_line():
    text, pos, _mode = _type("ab cd\nef\n", "gUU", 3)
    assert text == "AB CD\nef\n" and pos == 0
    assert _doc("ab\nef\n", "gUgU") == "AB\nef\n"
    assert _doc("AB\nef\n", "guu") == "ab\nef\n"
    assert _doc("AB\nef\n", "gugu") == "ab\nef\n"
    assert _doc("Ab\nef\n", "g~~") == "aB\nef\n"
    assert _doc("Ab\nef\n", "g~g~") == "aB\nef\n"


def test_case_operators_repeat_with_dot_and_undo_whole():
    assert _doc("ab cd\n", "gUiww.") == "AB CD\n"
    # gUU changes from the line's start, so that is where `u` lands.
    text, pos, _mode = _type("ab cd\n", "gUU" + "u", 3)
    assert text == "ab cd\n" and pos == 0


def test_a_mismatched_operator_pair_abandons_both():
    assert _doc("ab\n", "dgU") == "ab\n"
    assert _doc("ab\n", "gUd") == "ab\n"
    assert _doc("ab\n", "><") == "ab\n"


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
    # undo puts the caret back where the `x` was, and `.` takes it again.
    assert _doc("abcdef\n", "xu.") == "bcdef\n"


def test_dot_repeats_a_text_object_change():
    assert _doc("aaa bbb\n", "ciwZ" + _ESC + "w.") == "Z Z\n"


def test_dot_repeats_what_the_insert_leg_left_not_every_key_typed():
    # Backspace and Delete are part of the change. Replaying only the printable
    # keys would put the corrected-away characters back: `iab<BS>c` leaves "ac",
    # so `.` has to leave "ac" too, not "abc".
    assert _doc("one\ntwo\n", "iab" + _BS + "c" + _ESC + "j0.") == "acone\nactwo\n"
    assert _doc("one\ntwo\n", "ia" + _DEL + _ESC + "j0.") == "ane\nawo\n"


# ── `u` / `U` take one command at a time ──

def test_one_u_undoes_a_change_with_its_insert_leg():
    # `cw` removes, then typing inserts: two steps on Qt's undo stack, one
    # change to vim.
    assert _doc("aaa bbb", "cwfoo" + _ESC + "u") == "aaa bbb"
    assert _doc("aaa bbb", "cwfoo" + _ESC + "uU") == "foo bbb"


def test_u_steps_back_one_command_at_a_time():
    keys = "cwfoo" + _ESC + "wcwbar" + _ESC
    assert _doc("aaa bbb", keys) == "foo bar"
    assert _doc("aaa bbb", keys + "u") == "foo bbb"
    assert _doc("aaa bbb", keys + "uu") == "aaa bbb"
    assert _doc("aaa bbb", keys + "uuUU") == "foo bar"
    # A `.` that replays a change undoes as one change too.
    assert _doc("aaa bbb", "cwfoo" + _ESC + "w.u") == "foo bbb"


def test_undo_lands_the_caret_where_the_change_began():
    assert _type("a b c", "dwu") == ("a b c", 0, VimMode.NORMAL)
    assert _type("a b c", "dwuU") == ("b c", 0, VimMode.NORMAL)
    assert _type("aaa bbb", "cwfoo" + _ESC + "u")[1] == 0
    assert _type("abcdef", "xu", pos=3)[1] == 3


def test_undo_lands_the_caret_where_the_change_began_in_repeated_text():
    # The restored text repeats what follows it, so the first character that
    # differs comes after the change — the caret still goes back to where the
    # change began.
    assert _type("- item one\n- item two\n", "ddu")[1] == 0
    assert _type("p\n\n\nq\n", "jddu")[1] == 2
    assert _type("abc\n", "onew" + _ESC + "u") == ("abc\n", 0, VimMode.NORMAL)
    assert _type("aaa", "xu", pos=1)[1] == 1


# Each row was checked against vim 9.2: text, caret, keys, then where vim puts
# the caret after them.
_UNDO_CARETS = [
    # A change reaching left of the caret: back to the start of what it took.
    ("abcdef", 3, "Xu", 2),
    ("abc def", 5, "dbu", 4),
    ("abc def", 6, "d0u", 0),
    ("one two three", 12, "d2bu", 4),
    ("abc def", 6, "cbX" + _ESC + "u", 4),
    ("abcdef", 4, "vhhdu", 2),
    # An insert that moved first: back to where the typing went in.
    ("abc def", 1, "Afoo" + _ESC + "u", 6),
    ("abc def", 2, "Ifoo" + _ESC + "u", 0),
    ("abc def", 2, "afoo" + _ESC + "u", 3),
    # `o`, `O` and `J` change away from the caret, which stays.
    ("abc\nxyz\n", 2, "onew" + _ESC + "u", 2),
    ("abc\nxyz\n", 5, "Onew" + _ESC + "u", 5),
    ("ab\ncd\nef\n", 1, "Ju", 1),
    # Line-wise: `dd` and `cc` to the first non-blank, `dj`/`dk` keep the column.
    ("  abc\ndef\n", 3, "ddu", 2),
    ("abc\ndef\n", 5, "kddu", 0),
    ("  abc\n", 4, "ccx" + _ESC + "u", 2),
    ("  ab\ncd\n", 3, "dju", 3),
    ("ab\n  cd\nef\n", 5, "dku", 1),
    # Redo lands in the same place, kept on the line.
    ("abc def", 4, "dbu0U", 0),
    ("abcdef", 3, "XuU", 2),
    ("abc def", 1, "Afoo" + _ESC + "0uU", 7),
    ("  abc\ndef\n", 3, "dduU", 2),
]


def test_undo_and_redo_land_the_caret_where_vim_does():
    for text, pos, keys, caret in _UNDO_CARETS:
        assert _type(text, keys, pos)[1] == caret, (text, pos, keys)


def test_two_inserts_in_a_row_are_two_changes():
    # Qt would fold `bar` into the `foo` typing step, since it carries on
    # where `foo` ended; vim takes them back one at a time.
    keys = "ifoo" + _ESC + "abar" + _ESC
    assert _type("abc def", keys + "u") == ("fooabc def", 3, VimMode.NORMAL)
    assert _doc("abc def", keys + "uu") == "abc def"
    assert _doc("abc def", keys + "uuU") == "fooabc def"
    assert _doc("aaa bbb", "cwfoo" + _ESC + "abar" + _ESC + "u") == "foo bbb"


def test_an_undone_change_overwritten_by_new_edits_is_not_replayed():
    # After `u`, two new deletes reach the stack depth the undone `cw` once
    # spanned; one `u` must still take back only the last `x`.
    assert _doc("aaa bbb", "cwfoo" + _ESC + "uxxu") == "aa bbb"


def test_a_change_replacing_an_undone_one_is_undone_and_redone_whole():
    # The undone `x` ended at the depth the new `cw` starts from; its span must
    # not stand in for the `cw`'s, or `U` redoes only the removal.
    assert _doc("aaa bbb", "xu" + "cwfoo" + _ESC + "uU") == "foo bbb"
    # Nor may it hand its caret to a later change at the same depth.
    assert _type("aaa bbb ccc", "xwxuu" + "ww" + "xu")[1] == 8


def test_undo_takes_back_one_command_built_from_edit_blocks():
    # `J` is one edit block, which moves Qt's stack position by more than one;
    # `u` must still stop at the command's start, not count steps past it.
    assert _doc("a\nb\nc\n", "J.u") == "a b\nc\n"
    assert _doc("a\nb\nc\n", "J.uu") == "a\nb\nc\n"
    assert _doc("a\nb\nc\n", "J.uuUU") == "a b c\n"


def test_a_reload_forgets_the_undo_history():
    # textli reloads a file changed on disk with `setPlainText`, which clears
    # Qt's undo stack; nothing recorded before it may steer `u` or `U` after.
    _app()
    editor = QPlainTextEdit("aaa bbb")
    handler = VimKeyHandler(
        editor=editor, mode_changed=lambda m: None,
        close_save=lambda: None, close_cancel=lambda: None)

    def press(ch, mods=Qt.KeyboardModifier.NoModifier):
        key = (Qt.Key.Key_Escape if ch == _ESC
               else getattr(Qt.Key, f"Key_{ch.upper()}"))
        event = QKeyEvent(QEvent.Type.KeyPress, key, mods, ch)
        if not handler.handle_key(event):
            QPlainTextEdit.keyPressEvent(editor, event)

    def reload(text, caret):
        editor.setPlainText(text)
        cur = editor.textCursor()
        cur.setPosition(caret)
        editor.setTextCursor(cur)

    press("x")
    reload("xxx yyy zzz", 4)
    press("x")
    press("u")
    assert (editor.toPlainText(), editor.textCursor().position()) == (
        "xxx yyy zzz", 4)

    reload("aaa bbb", 0)
    for ch in "cwfoo" + _ESC + "u":
        press(ch)
    reload("one two three", 8)
    press("U", Qt.KeyboardModifier.ShiftModifier)
    assert (editor.toPlainText(), editor.textCursor().position()) == (
        "one two three", 8)


# ── VISUAL mode shares the motions and objects ──

def test_visual_takes_text_objects_and_find_motions():
    assert _doc(LINE, "viwd", 5) == "foo() baz\n"
    assert _doc(LINE, "vfrd") == ") baz\n"
    assert _doc(LINE, "vi(d", 5) == "foo() baz\n"


def test_visual_paste_replaces_the_selection():
    assert _doc("word here\n", "yiwwviwp") == "word word\n"


def test_visual_includes_the_character_under_the_caret():
    # Qt's selection is exclusive; vim's covers both ends (#77).
    assert _doc("abcdef", "vd") == "bcdef"
    assert _doc("abcdef", "vlld") == "def"
    assert _doc("abc", "vllyP") == "abcabc"
    assert _doc("abc def", "ved") == " def"
    assert _doc("abc\ndef", "vjd", 1) == "af"


def test_visual_l_stops_on_the_last_character_and_dollar_takes_the_newline():
    assert _doc("ab\ncd", "vllllld") == "\ncd"
    assert _doc("ab\ncd", "v$d") == "cd"


def test_visual_o_swaps_the_ends():
    assert _doc("abcdef", "vllohd", 1) == "ef"
    # Backward, then swapped back: the anchor end stays included.
    assert _doc("abcdef", "vhhold", 3) == "af"


def test_leaving_visual_keeps_the_caret_where_it_was():
    assert _type("abcdef", "vll" + _ESC) == ("abcdef", 2, VimMode.NORMAL)
    # `v$` reaches the line break; Esc steps back onto the last character.
    assert _type("abc\ndef", "v$" + _ESC) == ("abc\ndef", 2, VimMode.NORMAL)


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

    press(Qt.Key.Key_Greater, ">")           # > awaits its motion
    assert handler.has_pending
    press(Qt.Key.Key_Greater, ">")
    assert not handler.has_pending

    press(Qt.Key.Key_G, "g")                 # gU awaits its motion
    press(Qt.Key.Key_U, "U")
    assert handler.has_pending
    press(Qt.Key.Key_W, "w")
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
