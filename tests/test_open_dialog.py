"""The `go` open-file dialog: vim binding, overlay filtering, descend/complete,
and the in-place file switch (flush old, swap buffer, record history)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

from PySide6.QtCore import QEvent, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.editor import ZenMarkdownEditor  # noqa: E402
from textli.vim import VimKeyHandler, VimMode  # noqa: E402


def _ev(key, text=""):
    return QKeyEvent(QEvent.Type.KeyPress, key,
                     Qt.KeyboardModifier.NoModifier, text, False, 1)


def _editor(monkeypatch, file_path: Path, history=(), text="") -> ZenMarkdownEditor:
    """A file-backed editor whose history I/O is stubbed: reads the given
    list, records into ``ed._recorded`` — the user's real QSettings stay
    untouched."""
    QApplication.instance() or QApplication([])
    recorded = []
    monkeypatch.setattr(
        ZenMarkdownEditor, "_load_open_history",
        staticmethod(lambda: list(history)))
    monkeypatch.setattr(
        ZenMarkdownEditor, "_record_open_history",
        lambda self, p: recorded.append(Path(p)))
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, text, title="t", file_path=file_path)
    ed._parent = parent
    ed._recorded = recorded
    return ed


# ── vim binding ──

def test_go_opens_the_dialog(monkeypatch, tmp_path):
    f = tmp_path / "a.md"
    f.write_text("hi")
    ed = _editor(monkeypatch, f)
    assert ed._vim.handle_key(_ev(Qt.Key.Key_G, "g")) is True
    assert ed._vim.handle_key(_ev(Qt.Key.Key_O, "o")) is True
    assert ed._open_overlay is not None


def test_o_alone_still_opens_a_line(monkeypatch, tmp_path):
    f = tmp_path / "a.md"
    f.write_text("one line")
    ed = _editor(monkeypatch, f, text="one line")
    ed._vim.handle_key(_ev(Qt.Key.Key_O, "o"))
    assert ed._vim.mode == VimMode.INSERT
    assert ed._editor.toPlainText() == "one line\n"
    assert ed._open_overlay is None


def test_go_without_callback_is_a_quiet_noop():
    # InlineVimEditor-style hosts pass no open_file — `go` must not crash.
    from PySide6.QtWidgets import QPlainTextEdit
    QApplication.instance() or QApplication([])
    editor = QPlainTextEdit("text")
    vim = VimKeyHandler(editor=editor, mode_changed=lambda m: None,
                        close_save=lambda: None, close_cancel=lambda: None)
    assert vim.handle_key(_ev(Qt.Key.Key_G, "g")) is True
    assert vim.handle_key(_ev(Qt.Key.Key_O, "o")) is True
    assert vim.mode == VimMode.NORMAL          # not the plain `o` insert


def test_go_works_in_read_mode_and_stays_there(monkeypatch, tmp_path):
    a = tmp_path / "a.md"
    a.write_text("# A\n\ncontent A")
    b = tmp_path / "b.md"
    b.write_text("# B\n\ncontent B")
    ed = _editor(monkeypatch, a, history=[str(b)], text="# A\n\ncontent A")
    ed._toggle_rendered()
    assert ed._rendered_mode
    # go via the read view's g-pending
    assert ed._handle_rendered_key(_ev(Qt.Key.Key_G, "g")) is True
    assert ed._handle_rendered_key(_ev(Qt.Key.Key_O, "o")) is True
    assert ed._open_overlay is not None
    ov = ed._open_overlay
    ov._input.setText("b.md")
    ov._handle_key(_ev(Qt.Key.Key_Return))
    assert ed._file_path == b
    assert ed._rendered_mode                       # still reading
    assert "content B" in ed._rendered.toPlainText()
    assert ed._editor.toPlainText() == "# B\n\ncontent B"


# ── overlay: filtering, descend, complete ──

def test_history_fuzzy_suggests_file_and_dir(monkeypatch, tmp_path):
    f = tmp_path / "cur.md"
    f.write_text("x")
    ed = _editor(monkeypatch, f, history=["/mydocs/my_cool_doc1.md"])
    ed._open_file_dialog()
    ov = ed._open_overlay
    ov._input.setText("my")
    paths = [c.path for c in ov._rows]
    assert "/mydocs/my_cool_doc1.md" in paths
    assert "/mydocs/" in paths


def test_enter_on_dir_descends(monkeypatch, tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").touch()
    (tmp_path / "docs" / "sub").mkdir()
    f = tmp_path / "cur.md"
    f.write_text("x")
    ed = _editor(monkeypatch, f)
    ed._open_file_dialog()
    ov = ed._open_overlay
    ov._input.setText(f"{tmp_path}/do")
    assert [c.path for c in ov._rows] == [f"{tmp_path}/docs/"]
    ov._handle_key(_ev(Qt.Key.Key_Return))
    assert ov._input.text() == f"{tmp_path}/docs/"
    assert set(c.path for c in ov._rows) == {
        f"{tmp_path}/docs/sub/", f"{tmp_path}/docs/a.md"}


def test_tab_extends_to_common_prefix(monkeypatch, tmp_path):
    (tmp_path / "doc_plan.md").touch()
    (tmp_path / "doc_notes.md").touch()
    f = tmp_path / "cur.md"
    f.write_text("x")
    ed = _editor(monkeypatch, f)
    ed._open_file_dialog()
    ov = ed._open_overlay
    ov._input.setText(f"{tmp_path}/d")
    ov._handle_key(_ev(Qt.Key.Key_Tab))
    assert ov._input.text() == f"{tmp_path}/doc_"


def test_escape_cancels_back_to_editor(monkeypatch, tmp_path):
    f = tmp_path / "a.md"
    f.write_text("hi")
    ed = _editor(monkeypatch, f)
    ed._open_file_dialog()
    ed._open_overlay._handle_key(_ev(Qt.Key.Key_Escape))
    assert ed._open_overlay is None
    assert ed._file_path == f                  # nothing switched


# ── the switch itself ──

def test_choose_file_switches_buffer_and_records(monkeypatch, tmp_path):
    a = tmp_path / "a.md"
    a.write_text("content A")
    b = tmp_path / "b.md"
    b.write_text("content B")
    ed = _editor(monkeypatch, a, history=[str(b)], text="content A")
    opened = []
    ed.file_opened.connect(lambda p: opened.append(p))
    ed._open_file_dialog()
    ov = ed._open_overlay
    ov._input.setText("b.md")                  # bare word → history fuzzy
    assert [c.path for c in ov._rows][0] == str(b)
    ov._handle_key(_ev(Qt.Key.Key_Return))
    assert ed._open_overlay is None
    assert ed._file_path == b
    assert ed._editor.toPlainText() == "content B"
    assert opened == [b]
    assert ed._recorded[-1] == b               # history LRU updated


def test_switch_flushes_pending_edits_to_the_old_file(monkeypatch, tmp_path):
    a = tmp_path / "a.md"
    a.write_text("original")
    b = tmp_path / "b.md"
    b.write_text("B")
    ed = _editor(monkeypatch, a, text="original")
    ed._editor.textCursor().insertText("typed ")   # schedules an autosave
    ed._switch_file(b)
    assert a.read_text() == "typed original"       # flushed before the swap
    assert ed._editor.toPlainText() == "B"


def test_open_nonexistent_path_starts_empty_and_creates_nothing(
        monkeypatch, tmp_path):
    a = tmp_path / "a.md"
    a.write_text("A")
    ed = _editor(monkeypatch, a, text="A")
    new = tmp_path / "fresh.md"
    ed._switch_file(new)
    assert ed._editor.toPlainText() == ""
    assert ed._file_path == new
    # a mere open must not materialize the file — created on first save
    assert not new.exists()
    assert not (ed._autosave_timer and ed._autosave_timer.isActive())


def test_initial_open_lands_in_history(monkeypatch, tmp_path):
    f = tmp_path / "first.md"
    f.write_text("x")
    ed = _editor(monkeypatch, f)
    assert ed._recorded == [f]


# ── persistence (real QSettings, saved & restored) ──

def test_history_roundtrips_through_qsettings(tmp_path):
    QApplication.instance() or QApplication([])
    settings = QSettings("textli", "textli")
    saved = settings.value("open/history")
    try:
        settings.setValue("open/history", ["/x/a.md"])
        parent = QWidget()
        parent.resize(800, 600)
        f = tmp_path / "n.md"
        f.write_text("x")
        ed = ZenMarkdownEditor(parent, "x", title="t", file_path=f)
        ed._parent = parent
        hist = ed._load_open_history()
        assert hist[0] == str(f)               # recorded at construction
        assert "/x/a.md" in hist
    finally:
        if saved is None:
            settings.remove("open/history")
        else:
            settings.setValue("open/history", saved)
