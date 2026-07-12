"""The `/` search overlay: key routing in both views, live hit selection,
jump-on-Enter, Esc position restore, and n/N navigation with wrap."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.constants import (  # noqa: E402
    ZEN_SEARCH_CURRENT,
    ZEN_SEARCH_HIT,
    _CTRL_MOD,
)
from textli.editor import ZenMarkdownEditor  # noqa: E402
from textli.vim import VimMode  # noqa: E402

MD = ("# Title\n\n"
      "alpha paragraph mentioning pipeline here.\n\n"
      "beta paragraph, nothing else.\n\n"
      "gamma paragraph mentioning pipeline again.\n")


def _ev(key, text="", shift=False, ctrl=False):
    mods = Qt.KeyboardModifier.NoModifier
    if shift:
        mods |= Qt.KeyboardModifier.ShiftModifier
    if ctrl:
        mods |= _CTRL_MOD
    return QKeyEvent(QEvent.Type.KeyPress, key, mods, text, False, 1)


def _editor(text=MD, show=True) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(900, 600)
    if show:
        parent.show()
    ed = ZenMarkdownEditor(parent, text, title="t")
    ed._parent = parent
    return ed


# ── opening ──

def test_slash_opens_search_in_write_normal_mode():
    ed = _editor()
    assert ed._handle_key(_ev(Qt.Key.Key_Slash, "/")) is True
    assert ed._search_overlay is not None


def test_slash_types_literally_in_insert_mode():
    ed = _editor(text="")
    ed._vim.handle_key(_ev(Qt.Key.Key_I, "i"))
    assert ed._vim.mode == VimMode.INSERT
    assert ed._handle_key(_ev(Qt.Key.Key_Slash, "/")) is False  # falls through
    assert ed._search_overlay is None


def test_slash_opens_search_in_read_view():
    ed = _editor()
    ed._toggle_rendered()
    assert ed._handle_rendered_key(_ev(Qt.Key.Key_Slash, "/")) is True
    assert ed._search_overlay is not None


# ── the overlay ──

def test_typing_lists_hits_ranked_best_first():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")
    # both are substring hits; the shorter line noses ahead — and the best
    # match is pre-selected
    assert [h.line_no for h in ov.hits] == [2, 6]
    assert ov._sel == 0


def test_enter_jumps_to_the_match_and_highlights_it():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")
    first_hit = ov.hits[0]
    match_at = first_hit.start + first_hit.text.find("pipeline")
    ov._handle_key(_ev(Qt.Key.Key_Return))
    assert ed._search_overlay is None
    assert ed._search_query == "pipeline"
    # the caret lands on the match itself, vim-style
    assert ed._editor.textCursor().position() == match_at
    sels = ed._editor.extraSelections()
    assert len(sels) == 2
    colors = {s.format.background().color().rgba() for s in sels}
    assert ZEN_SEARCH_CURRENT.rgba() in colors
    assert ZEN_SEARCH_HIT.rgba() in colors
    # the wash covers the match region, not the whole line
    cur_sel = next(s for s in sels
                   if s.format.background().color().rgba()
                   == ZEN_SEARCH_CURRENT.rgba())
    assert cur_sel.cursor.selectionStart() == match_at
    assert cur_sel.cursor.selectionEnd() == match_at + len("pipeline")


def test_selection_moves_and_previews():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")
    ov._handle_key(_ev(Qt.Key.Key_Down))
    assert ov._sel == 1
    # live preview parked the caret on the selected hit's match
    h = ov.hits[1]
    assert ed._editor.textCursor().position() == \
        h.start + h.text.find("pipeline")


def test_emptying_the_query_clears_highlights():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")
    assert ed._editor.extraSelections() != []
    ov._input.setText("")                    # empty query = no search
    assert ov.hits == []
    assert ed._editor.extraSelections() == []


def test_escape_restores_position_and_clears_highlights():
    ed = _editor()
    cur = ed._editor.textCursor()
    cur.setPosition(5)
    ed._editor.setTextCursor(cur)
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")        # preview moved the caret
    ov._handle_key(_ev(Qt.Key.Key_Escape))
    assert ed._search_overlay is None
    assert ed._editor.textCursor().position() == 5
    assert ed._editor.extraSelections() == []


def test_card_flips_to_bottom_when_it_would_cover_a_top_hit():
    # A hit near the document top can't be scrolled below the card (the view
    # is already at scroll 0) — the card must move out of the way instead.
    md = "unique-needle right here\n\n" + "\n\n".join(
        f"filler paragraph {i}" for i in range(60))
    ed = _editor(text=md)
    ed._open_search()
    ov = ed._search_overlay
    assert ov.region == "top"
    ov._input.setText("unique-needle")
    assert ov.region == "bottom"
    # and the caret (on the hit) is now clear of the card
    vp_top = ed._editor.viewport().mapTo(ed, QPoint(0, 0)).y()
    assert ed._editor.cursorRect().bottom() + vp_top < ov.geometry().top()


def test_card_stays_on_top_for_a_scrollable_hit():
    md = "\n\n".join(f"filler paragraph {i}" for i in range(30)) + \
         "\n\nunique-needle mid document\n\n" + \
         "\n\n".join(f"tail paragraph {i}" for i in range(30))
    ed = _editor(text=md)
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("unique-needle")
    assert ov.region == "top"                    # scrolling could reveal it
    vp_top = ed._editor.viewport().mapTo(ed, QPoint(0, 0)).y()
    assert ed._editor.cursorRect().top() + vp_top > ov.geometry().bottom()


# ── n / N ──

def test_n_and_shift_n_step_with_wrap():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")
    h0, h1 = ov.hits
    m0 = h0.start + h0.text.find("pipeline")        # caret lands on the match
    m1 = h1.start + h1.text.find("pipeline")
    ov._handle_key(_ev(Qt.Key.Key_Return))          # at hit 0
    ed._handle_key(_ev(Qt.Key.Key_N, "n"))
    assert ed._editor.textCursor().position() == m1
    ed._handle_key(_ev(Qt.Key.Key_N, "n"))          # wraps forward
    assert ed._editor.textCursor().position() == m0
    ed._handle_key(_ev(Qt.Key.Key_N, "N", shift=True))   # wraps backward
    assert ed._editor.textCursor().position() == m1


def test_query_survives_view_toggle():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("pipeline")
    ov._handle_key(_ev(Qt.Key.Key_Return))
    ed._toggle_rendered()
    assert ed._rendered.extraSelections() == []     # stale offsets cleared
    ed._handle_rendered_key(_ev(Qt.Key.Key_N, "n"))
    pos = ed._rendered.textCursor().position()
    shown = ed._rendered.toPlainText()
    assert shown[pos:pos + 8] == "pipeline"          # caret on the match
    assert ed._rendered.extraSelections() != []


def test_n_without_query_is_a_noop():
    ed = _editor()
    before = ed._editor.textCursor().position()
    ed._handle_key(_ev(Qt.Key.Key_N, "n"))
    assert ed._editor.textCursor().position() == before


# ── replace (write view only, literal matches) ──

def test_tab_reveals_replace_in_write_view():
    ed = _editor()
    ed._open_search()
    ov = ed._search_overlay
    assert ov._allow_replace is True
    ov._input.setText("pipeline")
    ov._handle_key(_ev(Qt.Key.Key_Tab))
    assert ov._replace.isVisible()


def test_tab_is_a_noop_in_the_read_view():
    ed = _editor()
    ed._toggle_rendered()
    ed._open_search()
    ov = ed._search_overlay
    assert ov._allow_replace is False
    ov._input.setText("pipeline")
    ov._handle_key(_ev(Qt.Key.Key_Tab))
    assert not ov._replace.isVisible()          # read view stays find-only


def test_replace_all_replaces_every_literal_match_in_one_undo():
    ed = _editor(text="foo x foo\ny foo z\n")
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("foo")
    ov._handle_key(_ev(Qt.Key.Key_Tab))
    ov._replace.setText("BAR")
    ov._handle_replace_key(_ev(Qt.Key.Key_Return, ctrl=True))
    assert ed._editor.toPlainText() == "BAR x BAR\ny BAR z\n"
    ed._editor.undo()                           # one step restores everything
    assert ed._editor.toPlainText() == "foo x foo\ny foo z\n"


def test_replace_one_advances_and_is_per_match_undo():
    ed = _editor(text="foo a foo b foo\n")
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("foo")
    ov._handle_key(_ev(Qt.Key.Key_Tab))
    ov._replace.setText("X")
    ov._handle_replace_key(_ev(Qt.Key.Key_Return))
    assert ed._editor.toPlainText() == "X a foo b foo\n"
    ov._handle_replace_key(_ev(Qt.Key.Key_Return))   # advanced to the next
    assert ed._editor.toPlainText() == "X a X b foo\n"
    ed._editor.undo()                           # each replace is its own step
    assert ed._editor.toPlainText() == "X a foo b foo\n"


def test_replace_targets_literal_matches_case_insensitively():
    ed = _editor(text="The the THE done\n")
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("the")
    ov._handle_key(_ev(Qt.Key.Key_Tab))
    ov._replace.setText("z")
    ov._handle_replace_key(_ev(Qt.Key.Key_Return, ctrl=True))
    assert ed._editor.toPlainText() == "z z z done\n"


def test_esc_after_a_replace_stays_put():
    ed = _editor(text="foo bar foo\n")
    ed._open_search()
    ov = ed._search_overlay
    ov._input.setText("foo")
    ov._handle_key(_ev(Qt.Key.Key_Tab))
    ov._replace.setText("X")
    ov._handle_replace_key(_ev(Qt.Key.Key_Return))
    ov._handle_replace_key(_ev(Qt.Key.Key_Escape))
    assert ed._search_overlay is None
    assert ed._search_saved is None             # a replace happened — no restore
