"""Position memory: reopening a file resumes the stored view mode, caret and
read-view scroll; explicit targets (-r, #anchor) override; `go` restores
offsets but keeps the current view. Plus typewriter scrolling (⌘T)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.editor import ZenMarkdownEditor  # noqa: E402

LONG = "# Top\n\n" + "a line of steady prose\n" * 80 + "\n## Deep\n\nend here\n"


def _editor(monkeypatch, store, path, text=LONG, **kwargs):
    """A file-backed editor whose position + history I/O is stubbed onto
    ``store`` (a plain list) — the user's real QSettings stay untouched."""
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(ZenMarkdownEditor, "_load_positions",
                        staticmethod(lambda: list(store)))

    def _st(entries):
        store[:] = entries
    monkeypatch.setattr(ZenMarkdownEditor, "_store_positions",
                        staticmethod(_st))
    monkeypatch.setattr(ZenMarkdownEditor, "_record_open_history",
                        lambda self, p: None)
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    ed = ZenMarkdownEditor(parent, text, title="T", file_path=path, **kwargs)
    ed._parent = parent
    return ed


def _park_caret(ed, pos):
    cur = ed._editor.textCursor()
    cur.setPosition(pos)
    ed._editor.setTextCursor(cur)


def test_write_caret_is_restored_on_reopen(monkeypatch, tmp_path):
    store: list = []
    f = tmp_path / "a.md"
    ed = _editor(monkeypatch, store, f)
    _park_caret(ed, 120)
    ed._save_position()
    assert store, "position was persisted"
    ed2 = _editor(monkeypatch, store, f)
    assert ed2._rendered_mode is False
    assert ed2._editor.textCursor().position() == 120


def test_read_mode_and_scroll_are_restored(monkeypatch, tmp_path):
    store: list = []
    f = tmp_path / "b.md"
    ed = _editor(monkeypatch, store, f)
    ed._toggle_rendered()
    sb = ed._rendered.verticalScrollBar()
    sb.setValue(sb.maximum() // 2)          # mid-document
    top_before = ed._rendered.cursorForPosition(
        ed._rendered.viewport().rect().topLeft()).position()
    assert top_before > 0
    ed._save_position()
    ed2 = _editor(monkeypatch, store, f)
    assert ed2._rendered_mode is True       # reopened straight into reading
    top_after = ed2._rendered.cursorForPosition(
        ed2._rendered.viewport().rect().topLeft()).position()
    # same neighbourhood (block-snapped, so allow a line of slack)
    assert abs(top_after - top_before) < 60


def test_anchor_overrides_remembered_offsets(monkeypatch, tmp_path):
    store: list = []
    f = tmp_path / "c.md"
    ed = _editor(monkeypatch, store, f)
    _park_caret(ed, 120)
    ed._save_position()
    ed2 = _editor(monkeypatch, store, f, anchor="deep")
    # the anchor put the caret on the "## Deep" heading, not back at 120
    line = ed2._editor.textCursor().block().text()
    assert "Deep" in line


def test_explicit_read_flag_still_wins(monkeypatch, tmp_path):
    store: list = []
    f = tmp_path / "d.md"
    ed = _editor(monkeypatch, store, f)     # left in *write* mode
    ed._save_position()
    ed2 = _editor(monkeypatch, store, f, start_in_read=True)
    assert ed2._rendered_mode is True       # -r forced reading regardless


def test_switch_file_restores_offsets_but_keeps_view(monkeypatch, tmp_path):
    store: list = []
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    b.write_text(LONG, encoding="utf-8")
    # leave b remembered in READ mode with a caret
    ed = _editor(monkeypatch, store, b)
    ed._toggle_rendered()
    ed._save_position()
    # now open a in write mode and `go` to b
    ed2 = _editor(monkeypatch, store, a)
    ed2._switch_file(b)
    assert ed2._rendered_mode is False      # go stays in the invoking view
    # and leaving a remembered where it was
    from textli import positions
    assert positions.lookup(store, str(a)) is not None


def test_hide_saves_the_position(monkeypatch, tmp_path):
    store: list = []
    f = tmp_path / "e.md"
    ed = _editor(monkeypatch, store, f)
    _park_caret(ed, 50)
    ed.hide()
    from textli import positions
    assert positions.lookup(store, str(f)) == ("write", 50, 0)


# ── typewriter scrolling (⌘T) ──

def test_typewriter_holds_the_caret_line(monkeypatch, tmp_path):
    store: list = []
    f = tmp_path / "t.md"
    ed = _editor(monkeypatch, store, f)
    # what _toggle_typewriter does, minus the QSettings write (real settings
    # stay untouched in tests)
    ed._typewriter = True
    ed._editor.setCenterOnScroll(True)
    cur = ed._editor.textCursor()
    cur.movePosition(cur.MoveOperation.End)
    ed._editor.setTextCursor(cur)           # recenter fires on the move
    y = ed._editor.cursorRect().center().y()
    target = int(ed._editor.viewport().height() * 0.42)
    line_h = ed._editor.fontMetrics().lineSpacing()
    assert abs(y - target) <= line_h        # held at the typewriter line


def test_typewriter_off_leaves_scrolling_alone(monkeypatch, tmp_path):
    store: list = []
    f = tmp_path / "u.md"
    ed = _editor(monkeypatch, store, f)
    ed._typewriter = False                  # force off for the behaviour test
    cur = ed._editor.textCursor()
    cur.movePosition(cur.MoveOperation.End)
    ed._editor.setTextCursor(cur)
    y = ed._editor.cursorRect().center().y()
    target = int(ed._editor.viewport().height() * 0.42)
    assert y > target                       # caret rides low, page didn't chase
