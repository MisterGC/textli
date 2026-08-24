"""Fullscreen (F11 / ⌘⇧F): textli fills the screen, the OS chrome steps out.

The toggle acts on the editor's *window*, not on the editor widget, so it
behaves the same standalone and embedded; the preference persists, but only the
standalone host acts on it at startup.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli import settings as md_settings  # noqa: E402
from textli.constants import _CTRL_MOD  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402

MD = "# Heading\n\nSome text.\n"

_CTRL_SHIFT = _CTRL_MOD | Qt.KeyboardModifier.ShiftModifier


def _editor() -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, MD, title="T")
    ed._parent = parent  # keep a ref alive
    return ed


def _press(ed, key, mod=Qt.KeyboardModifier.NoModifier):
    return ed._handle_key(QKeyEvent(QEvent.Type.KeyPress, key, mod))


def test_f11_toggles_the_window_fullscreen_and_back():
    ed = _editor()
    win = ed.window()
    assert not win.isFullScreen()

    assert _press(ed, Qt.Key.Key_F11)
    assert win.isFullScreen()

    assert _press(ed, Qt.Key.Key_F11)
    assert not win.isFullScreen()


def test_ctrl_shift_f_toggles_fullscreen_too():
    ed = _editor()
    win = ed.window()

    assert _press(ed, Qt.Key.Key_F, _CTRL_SHIFT)
    assert win.isFullScreen()
    assert _press(ed, Qt.Key.Key_F, _CTRL_SHIFT)
    assert not win.isFullScreen()


def test_fullscreen_acts_on_the_window_not_the_editor_widget():
    # Embedded, the editor is a child widget — the toggle must reach past it to
    # the top-level window rather than fullscreening itself.
    ed = _editor()
    assert ed.window() is not ed
    _press(ed, Qt.Key.Key_F11)
    assert ed.window().isFullScreen()
    assert not ed.isFullScreen()


def test_works_in_the_read_view_and_beats_ctrl_f_page_down():
    # The read view's plain ⌘F pages down and doesn't exclude Shift, so the
    # global fullscreen branch has to be reached first (as ⌘⇧P does vs ⌘P).
    ed = _editor()
    ed._toggle_rendered()
    assert ed._rendered_mode
    before = ed._rendered.textCursor().position()

    assert _press(ed, Qt.Key.Key_F, _CTRL_SHIFT)
    assert ed.window().isFullScreen()
    assert ed._rendered.textCursor().position() == before   # never paged


def test_leaving_fullscreen_restores_a_maximized_window_as_maximized():
    ed = _editor()
    win = ed.window()
    win.showMaximized()
    assert win.isMaximized()

    _press(ed, Qt.Key.Key_F11)
    assert win.isFullScreen()
    # isMaximized() reads False while fullscreen — the state has to have been
    # captured on the way in.
    _press(ed, Qt.Key.Key_F11)
    assert not win.isFullScreen()
    assert win.isMaximized()


def test_leaving_fullscreen_restores_a_normal_window_as_normal():
    ed = _editor()
    win = ed.window()
    win.showNormal()

    _press(ed, Qt.Key.Key_F11)
    _press(ed, Qt.Key.Key_F11)
    assert not win.isFullScreen()
    assert not win.isMaximized()


def test_the_preference_persists_both_ways():
    ed = _editor()
    settings = md_settings.app_settings()

    _press(ed, Qt.Key.Key_F11)
    assert settings.value("zen_md/fullscreen", False, type=bool) is True

    _press(ed, Qt.Key.Key_F11)
    assert settings.value("zen_md/fullscreen", False, type=bool) is False


def test_standalone_host_reopens_fullscreen_when_that_is_how_it_was_left(tmp_path):
    from textli.app import TextliHost

    QApplication.instance() or QApplication([])
    md_settings.app_settings().setValue("zen_md/fullscreen", True)
    path = tmp_path / "note.md"
    path.write_text(MD, encoding="utf-8")

    host = TextliHost()
    host.showMaximized()
    host.open(Path(path), MD)
    assert host.isFullScreen()
    host.close()


def test_hidden_host_stays_hidden_so_pdf_export_is_headless(tmp_path):
    # `--pdf` opens the editor on a host it never shows; restoring fullscreen
    # there would put the export on screen.
    from textli.app import TextliHost

    QApplication.instance() or QApplication([])
    md_settings.app_settings().setValue("zen_md/fullscreen", True)
    path = tmp_path / "note.md"
    path.write_text(MD, encoding="utf-8")

    host = TextliHost()
    host.resize(1000, 1400)
    host.open(Path(path), MD, read=True)
    assert not host.isVisible()
    assert not host.isFullScreen()
    host.close()
