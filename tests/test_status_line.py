"""The whisper status line: faint per-view info in the card's corner —
mode/words/delta while writing, progress/time-left/review counts while
reading — hidden whenever an overlay card is up."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.editor import ZenMarkdownEditor  # noqa: E402

MD = "# Title\n\nthe {~~quick~>swift~~} fox {==jumps==}{>>really?<<} far\n"


def _editor(text=MD) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, text, title="T")
    ed._parent = parent
    return ed


def _key(ed, key, text=""):
    ev = QKeyEvent(QEvent.Type.KeyPress, key,
                   Qt.KeyboardModifier.NoModifier, text, False, 1)
    return ed._handle_key(ev)


def test_write_view_shows_mode_and_word_count():
    ed = _editor("some plain words here\n")
    s = ed._status_label.text()
    assert s == "NORMAL · 4 words"
    _key(ed, Qt.Key.Key_I, "i")            # enter INSERT
    assert ed._status_label.text().startswith("INSERT")
    assert not ed._status_label.isHidden()


def test_write_view_session_delta_appears_after_edits():
    ed = _editor("some plain words here\n")
    cur = ed._editor.textCursor()
    cur.movePosition(cur.MoveOperation.End)
    cur.insertText("and three words more\n")
    ed._refresh_status()                   # bypass the debounce timer
    assert ed._status_label.text() == "NORMAL · 8 words · +4"


def test_read_view_shows_progress_and_review_counts():
    ed = _editor()
    ed._toggle_rendered()
    s = ed._status_label.text()
    assert "%" in s
    assert "1 change" in s and "1 comment" in s
    # words: the accepted prose ("Title / the swift fox jumps far" = 7 words)
    # is short — no minutes-left whisper on a fully visible document.


def test_status_hides_while_an_overlay_is_open_and_returns():
    ed = _editor()
    assert not ed._status_label.isHidden()
    _key(ed, Qt.Key.Key_Slash, "/")        # search overlay opens
    assert ed._status_label.isHidden()
    ed._search_cancel()                    # Esc from the search card
    assert not ed._status_label.isHidden()


def test_visual_mode_is_whispered_in_read_view():
    ed = _editor()
    ed._toggle_rendered()
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_V,
                   Qt.KeyboardModifier.NoModifier, "v", False, 1)
    ed._handle_rendered_key(ev)
    assert ed._status_label.text().startswith("VISUAL · ")
    ed._handle_rendered_key(QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_V,
        Qt.KeyboardModifier.NoModifier, "v", False, 1))
    assert not ed._status_label.text().startswith("VISUAL")
