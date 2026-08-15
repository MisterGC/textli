"""textli standalone launcher: location (``path#heading-slug``) + read/write
mode, for the CLI and the host API."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from textli import positions as md_positions  # noqa: E402
from textli import app as app_mod  # noqa: E402
from textli.app import TextliHost, main as app_main, split_location  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402

MD = (
    "# Intro\n\nbody intro.\n\n"
    "## Design Decisions\n\nbody design.\n\n"
    "## Final Notes\n\nbody final.\n"
)


# ── location parsing ──

def test_split_location_plain_path():
    assert split_location("notes.md") == ("notes.md", "")


def test_split_location_with_anchor():
    assert split_location("notes.md#design-decisions") == (
        "notes.md", "design-decisions",
    )


def test_split_location_only_first_hash_starts_fragment():
    # slugs are [a-z0-9-]; the first '#' begins the fragment
    assert split_location("a.md#one#two") == ("a.md", "one#two")


# ── host forwards location + mode to the editor ──

def _host(monkeypatch):
    QApplication.instance() or QApplication([])
    # These editors are file-backed ("notes.md"), so position memory kicks
    # in — stub it or a torn-down read-mode editor from one test bleeds a
    # stored "read" record into the next (and the user's real QSettings).
    monkeypatch.setattr(ZenMarkdownEditor, "_load_positions",
                        staticmethod(lambda: []))
    monkeypatch.setattr(ZenMarkdownEditor, "_store_positions",
                        staticmethod(lambda e: None))
    monkeypatch.setattr(ZenMarkdownEditor, "_record_open_history",
                        lambda self, p: None)
    host = TextliHost()
    host.resize(800, 600)
    host.show()
    return host


def test_host_open_read_mode_at_anchor(monkeypatch):
    host = _host(monkeypatch)
    host.open(Path("notes.md"), MD, anchor="design-decisions", read=True)
    ed = host._editor
    assert ed._rendered_mode is True                 # opened in the read view
    block = ed._rendered.textCursor().block()
    assert block.blockFormat().headingLevel() == 2   # caret on the heading
    assert block.text() == "Design Decisions"


def test_host_open_write_mode_at_anchor(monkeypatch):
    host = _host(monkeypatch)
    host.open(Path("notes.md"), MD, anchor="final-notes", read=False)
    ed = host._editor
    assert ed._rendered_mode is False                # editable write view
    assert ed._editor.textCursor().block().text() == "## Final Notes"


def test_host_open_defaults_to_read_no_anchor(monkeypatch):
    # #58 — reading is now the default; writing is what `-w` asks for.
    host = _host(monkeypatch)
    host.open(Path("notes.md"), MD)
    assert host._editor._rendered_mode is True


# ── the default view vs. the file's remembered one (#58) ──

def _host_remembering(monkeypatch, mode: str):
    """A host whose position store already holds ``notes.md`` in ``mode``."""
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        ZenMarkdownEditor, "_load_positions",
        staticmethod(lambda: [md_positions.encode(
            str(Path("notes.md")), mode, 0, 0)]))
    monkeypatch.setattr(ZenMarkdownEditor, "_store_positions",
                        staticmethod(lambda e: None))
    monkeypatch.setattr(ZenMarkdownEditor, "_record_open_history",
                        lambda self, p: None)
    host = TextliHost()
    host.resize(800, 600)
    host.show()
    return host


def test_a_file_left_writing_comes_back_writing(monkeypatch):
    """The restore only ever toggled *into* read — the other direction came
    free from the app opening in write. With reading the default, a file left
    writing has to be carried back, or the resume holds one way only."""
    host = _host_remembering(monkeypatch, "write")
    host.open(Path("notes.md"), MD, read=True, stored_view_wins=True)
    assert host._editor._rendered_mode is False


def test_a_file_left_reading_comes_back_reading(monkeypatch):
    host = _host_remembering(monkeypatch, "read")
    host.open(Path("notes.md"), MD, read=True, stored_view_wins=True)
    assert host._editor._rendered_mode is True


def test_an_explicit_view_beats_the_remembered_one(monkeypatch):
    # `-w` on a file last left reading still opens writing...
    host = _host_remembering(monkeypatch, "read")
    host.open(Path("notes.md"), MD, read=False, stored_view_wins=False)
    assert host._editor._rendered_mode is False
    # ...and `-r` on one last left writing still opens reading.
    host2 = _host_remembering(monkeypatch, "write")
    host2.open(Path("notes.md"), MD, read=True, stored_view_wins=False)
    assert host2._editor._rendered_mode is True


# ── the CLI's flags map onto those two knobs ──

class _Opened(Exception):
    """Raised in place of opening a window, to stop ``main()`` at the point
    the view has been decided. Not SystemExit — argparse raises that, and a
    usage error must stay distinguishable from a successful parse."""


def _cli(monkeypatch, tmp_path, *flags):
    """Run ``main()`` far enough to see what it asks the host for.

    ``open`` is the last call before the event loop, so capturing there
    exercises the real argument parsing. ``main()`` builds its own
    ``QApplication``, which Qt refuses while the suite's still exists — hand
    it the live one instead.
    """
    existing = QApplication.instance() or QApplication([])
    note = tmp_path / "notes.md"
    note.write_text(MD, encoding="utf-8")
    captured = {}

    def fake_open(self, path, text, anchor="", read=True,
                  stored_view_wins=None):
        captured.update(read=read, stored_view_wins=stored_view_wins)
        raise _Opened

    monkeypatch.setattr(app_mod, "QApplication", lambda *a, **k: existing)
    monkeypatch.setattr(TextliHost, "open", fake_open)
    monkeypatch.setattr(TextliHost, "showMaximized", lambda self: None)
    monkeypatch.setattr(sys, "argv", ["textli", *flags, str(note)])
    try:
        app_main()
    except _Opened:
        pass
    return captured


def test_cli_without_a_flag_reads_and_lets_memory_win(monkeypatch, tmp_path):
    assert _cli(monkeypatch, tmp_path) == {
        "read": True, "stored_view_wins": True}


def test_cli_write_flag_forces_the_write_view(monkeypatch, tmp_path):
    assert _cli(monkeypatch, tmp_path, "-w") == {
        "read": False, "stored_view_wins": False}


def test_cli_read_flag_still_forces_the_read_view(monkeypatch, tmp_path):
    # kept working so an existing alias or script doesn't break
    assert _cli(monkeypatch, tmp_path, "--read") == {
        "read": True, "stored_view_wins": False}


def test_cli_rejects_asking_for_both_views(monkeypatch, tmp_path):
    with pytest.raises(SystemExit) as exc:
        _cli(monkeypatch, tmp_path, "-r", "-w")
    assert exc.value.code == 2          # argparse usage error, not a crash


# ── Esc: an exit for a host, a step back for the reader (#63) ──

def _press_escape(ed):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    return ed._handle_key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                                    Qt.KeyboardModifier.NoModifier))


def test_an_embedded_editor_still_hands_back_on_escape(monkeypatch, tmp_path):
    """The host contract must not move: embedded, the editor is modal and Esc
    is how it gives control back."""
    from PySide6.QtTest import QTest
    host = _host(monkeypatch)
    note = tmp_path / "notes.md"
    note.write_text(MD, encoding="utf-8")
    ed = ZenMarkdownEditor(host, MD, title="T", file_path=note)
    ed.resize(800, 600)
    ed._opacity.setOpacity(1.0)
    seen = []
    ed.cancelled.connect(lambda: seen.append("cancelled"))
    _press_escape(ed)
    QTest.qWait(600)              # the close fades out before it emits
    assert seen == ["cancelled"]


def test_the_standalone_app_does_not_quit_on_escape(monkeypatch, tmp_path):
    from PySide6.QtTest import QTest
    _host(monkeypatch)            # stub position memory
    note = tmp_path / "notes.md"
    note.write_text(MD, encoding="utf-8")
    host = TextliHost()
    host.resize(800, 600)
    host.show()
    host.open(note, MD)
    ed = host._editor
    ed._opacity.setOpacity(1.0)
    seen = []
    ed.cancelled.connect(lambda: seen.append("cancelled"))
    _press_escape(ed)
    QTest.qWait(600)
    assert seen == []
    assert host.isVisible()


def test_escape_says_how_to_quit_instead(monkeypatch, tmp_path):
    _host(monkeypatch)
    note = tmp_path / "notes.md"
    note.write_text(MD, encoding="utf-8")
    host = TextliHost()
    host.resize(800, 600)
    host.show()
    host.open(note, MD)
    ed = host._editor
    ed._opacity.setOpacity(1.0)
    _press_escape(ed)
    assert ed._mode_flash is not None
    assert "QUIT" in ed._mode_flash.text()


def test_the_standalone_host_binds_a_quit_shortcut(monkeypatch, tmp_path):
    """Esc used to be the only keyboard exit — on Linux and Windows the close
    button would otherwise be the only way out."""
    from PySide6.QtGui import QShortcut
    _host(monkeypatch)
    note = tmp_path / "notes.md"
    note.write_text(MD, encoding="utf-8")
    host = TextliHost()
    host.open(note, MD)
    bound = {s.key().toString() for s in host.findChildren(QShortcut)}
    assert any("Q" in b for b in bound), bound


def test_escape_still_backs_out_of_visual_mode_standalone(monkeypatch, tmp_path):
    """Esc keeps its real job — it just stops falling through to an exit."""
    _host(monkeypatch)
    note = tmp_path / "notes.md"
    note.write_text(MD, encoding="utf-8")
    host = TextliHost()
    host.resize(800, 600)
    host.show()
    host.open(note, MD, read=True)
    ed = host._editor
    ed._opacity.setOpacity(1.0)
    ed._set_visual(True)
    assert ed._visual is True
    _press_escape(ed)
    assert ed._visual is False
