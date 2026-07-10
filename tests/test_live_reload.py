"""Live reload (#23): the open file reflects external edits in place. A clean
buffer reloads, keeping the view, caret and scroll; unsaved local edits turn an
external change into a conflict that warns and keeps the buffer; the editor's
own writes never count as external. The watcher decision is driven directly
(`_reload_if_changed`) so the tests don't hang on the async QFileSystemWatcher."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.editor import ZenMarkdownEditor  # noqa: E402

BASE = "# Title\n\n" + "steady prose line\n" * 40 + "\n## Coda\n\ntail\n"


def _editor(monkeypatch, path, text=BASE):
    """A file-backed editor whose history I/O is stubbed; QSettings are already
    redirected to a tmp dir by conftest, so nothing touches real preferences."""
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(ZenMarkdownEditor, "_record_open_history",
                        lambda self, p: None)
    parent = QWidget()
    parent.resize(1000, 700)
    parent.show()
    path.write_text(text, encoding="utf-8")
    ed = ZenMarkdownEditor(parent, text, title="T", file_path=path)
    ed._parent = parent
    ed._last_notice = ""            # ignore any construction-time toast
    return ed


def test_watch_stays_armed_alongside_autosave(monkeypatch, tmp_path):
    f = tmp_path / "a.md"
    ed = _editor(monkeypatch, f)
    # the watcher used to be disarmed by _enable_autosave — it must stay live
    assert str(f) in ed._watcher.files()


def test_clean_buffer_reloads_external_edit(monkeypatch, tmp_path):
    f = tmp_path / "b.md"
    ed = _editor(monkeypatch, f)
    f.write_text(BASE.replace("# Title", "# Rewritten"), encoding="utf-8")
    ed._reload_if_changed()
    assert ed._editor.toPlainText().startswith("# Rewritten")
    assert "reloaded" in ed._last_notice
    # snapshot advanced, so a following identical event is a no-op
    assert ed._disk_snapshot == ed._editor.toPlainText()


def test_reload_keeps_read_view_and_rerenders(monkeypatch, tmp_path):
    f = tmp_path / "c.md"
    ed = _editor(monkeypatch, f)
    ed._toggle_rendered()
    assert ed._rendered_mode
    f.write_text(BASE.replace("## Coda", "## Freshly"), encoding="utf-8")
    ed._reload_if_changed()
    assert ed._rendered_mode                       # still reading
    rendered = ed._rendered.document().toPlainText()
    assert "Freshly" in rendered and "Coda" not in rendered


def test_reload_preserves_write_caret(monkeypatch, tmp_path):
    f = tmp_path / "g.md"
    ed = _editor(monkeypatch, f)
    cur = ed._editor.textCursor()
    cur.setPosition(60)
    ed._editor.setTextCursor(cur)                  # caret only — buffer stays clean
    f.write_text(BASE.replace("steady", "flowing"), encoding="utf-8")
    ed._reload_if_changed()
    assert ed._editor.toPlainText().count("flowing") > 0
    assert ed._editor.textCursor().position() == 60


def test_conflict_keeps_local_edits(monkeypatch, tmp_path):
    f = tmp_path / "d.md"
    ed = _editor(monkeypatch, f)
    ed._editor.setPlainText("# My local draft\n\nmine\n")   # unsaved divergence
    ed._autosave_timer.stop()                      # keep it unsaved
    f.write_text("# Their version\n\ntheirs\n", encoding="utf-8")
    ed._reload_if_changed()
    assert ed._editor.toPlainText().startswith("# My local draft")   # kept
    assert "kept your edits" in ed._last_notice


def test_own_autosave_is_not_seen_as_external(monkeypatch, tmp_path):
    f = tmp_path / "e.md"
    ed = _editor(monkeypatch, f)
    ed._editor.setPlainText("# Edited by me\n\nbody\n")
    ed._autosave()                                 # we own this write
    before = ed._editor.toPlainText()
    ed._last_notice = ""
    ed._reload_if_changed()                        # the watcher echo of our write
    assert ed._editor.toPlainText() == before      # untouched
    assert ed._last_notice == ""                   # no reload / conflict toast


def test_reload_from_disk_does_not_reschedule_autosave(monkeypatch, tmp_path):
    f = tmp_path / "h.md"
    ed = _editor(monkeypatch, f)
    ed._autosave_timer.stop()
    f.write_text(BASE.replace("# Title", "# New"), encoding="utf-8")
    ed._reload_if_changed()
    # the reload replaced the buffer but must not queue a write-back
    assert not ed._autosave_timer.isActive()
