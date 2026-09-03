"""The document's frontmatter status in the reading view: the whisper shows
what the document carries, `gs` picks a new value from the ones it declares,
and Enter writes it to disk (#69)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tomllib  # noqa: E402
from pathlib import Path  # noqa: E402

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli import status as md_status  # noqa: E402
from textli.editor import ZenMarkdownEditor  # noqa: E402

DECLARED = ("---\ntitle: Doc\nstatus: draft\nstatuses: draft, review, final\n"
            "---\n\n# Title\n\nSome body words here.\n")
PLAIN = "---\ntitle: Doc\n---\n\n# Title\n\nSome body words here.\n"


def _editor(text, tmp_path=None) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    path = None
    if tmp_path is not None:
        path = Path(tmp_path) / "doc.md"
        path.write_text(text, encoding="utf-8")
    ed = ZenMarkdownEditor(parent, text, title="T", file_path=path)
    ed._parent = parent
    if not ed._rendered_mode:
        ed._toggle_rendered()
    return ed


def _key(ed, key, text=""):
    return ed._handle_key(QKeyEvent(QEvent.Type.KeyPress, key,
                                    Qt.KeyboardModifier.NoModifier,
                                    text, False, 1))


def _gs(ed):
    _key(ed, Qt.Key.Key_G, "g")
    _key(ed, Qt.Key.Key_S, "s")


def _rows(ed) -> list[str]:
    """The value on each row of the open picker, in the order shown."""
    html = ed._status_picker.text()
    return [cell.split("&nbsp;&nbsp;", 1)[1].split("<", 1)[0]
                .replace("&nbsp;", "").strip()
            for cell in html.split("<tr><td")[1:]]


# ── The PySide6 floor (Qt 6.8 parks frontmatter in metadata) ────────

def test_qt_keeps_frontmatter_off_the_page():
    QApplication.instance() or QApplication([])
    doc = QTextDocument()
    doc.setMarkdown(DECLARED)
    assert "statuses" not in doc.toPlainText()
    assert doc.metaInformation(
        QTextDocument.MetaInformation.FrontMatter).startswith("title: Doc")


def test_the_declared_pyside6_floor_is_the_version_that_does_that():
    meta = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert "PySide6>=6.8" in meta["project"]["dependencies"]


# ── The whisper ────────────────────────────────────────────────────

def test_the_whisper_shows_the_status_a_document_declares():
    ed = _editor(DECLARED)
    assert ed._status_label.text().endswith("· status: draft")


def test_a_document_without_the_line_adds_nothing_to_the_whisper():
    ed = _editor(PLAIN)
    assert "status:" not in ed._status_label.text()


def test_declared_but_unset_whispers_the_empty_state():
    ed = _editor(DECLARED.replace("status: draft\n", ""))
    assert ed._status_label.text().endswith(f"· status: {md_status.UNSET}")


# ── `gs` ───────────────────────────────────────────────────────────

def test_gs_lists_the_declared_values_in_order_starting_on_the_current_one():
    ed = _editor(DECLARED.replace("status: draft", "status: review"))
    _gs(ed)
    assert ed._status_picker is not None
    assert _rows(ed) == ["draft", "review", "final"]
    assert ed._status_sel == 1           # opens on `review`, the current one


def test_gs_on_a_document_that_declares_nothing_opens_no_picker():
    ed = _editor(PLAIN)
    _gs(ed)
    assert ed._status_picker is None
    assert "statuses:" in ed._last_notice


def test_enter_sets_the_selected_value_and_saves_the_file(tmp_path):
    ed = _editor(DECLARED, tmp_path)
    _gs(ed)
    _key(ed, Qt.Key.Key_J, "j")          # draft → review
    _key(ed, Qt.Key.Key_J, "j")          # review → final
    _key(ed, Qt.Key.Key_Return)
    assert ed._status_picker is None
    assert "status: final" in ed._editor.toPlainText()
    assert "status: final" in (tmp_path / "doc.md").read_text()
    assert ed._status_label.text().endswith("· status: final")


def test_a_digit_picks_a_value_directly(tmp_path):
    ed = _editor(DECLARED, tmp_path)
    _gs(ed)
    _key(ed, Qt.Key.Key_3, "3")
    assert "status: final" in (tmp_path / "doc.md").read_text()


def test_esc_leaves_the_status_as_it_was(tmp_path):
    ed = _editor(DECLARED, tmp_path)
    _gs(ed)
    _key(ed, Qt.Key.Key_J, "j")
    _key(ed, Qt.Key.Key_Escape)
    assert ed._status_picker is None
    assert "status: draft" in (tmp_path / "doc.md").read_text()


def test_the_whisper_hides_while_the_picker_is_up():
    ed = _editor(DECLARED)
    assert not ed._status_label.isHidden()
    _gs(ed)
    assert ed._status_label.isHidden()
    _key(ed, Qt.Key.Key_Escape)
    assert not ed._status_label.isHidden()


def test_setting_the_status_is_one_undo_step():
    ed = _editor(DECLARED)
    _gs(ed)
    _key(ed, Qt.Key.Key_J, "j")
    _key(ed, Qt.Key.Key_Return)
    assert "status: review" in ed._editor.toPlainText()
    ed._editor.undo()
    assert "status: draft" in ed._editor.toPlainText()


def test_the_page_stays_where_it_was():
    # Frontmatter never reaches the page, so nothing the reader sees moves.
    ed = _editor(DECLARED)
    before = ed._rendered.document().toPlainText()
    _gs(ed)
    _key(ed, Qt.Key.Key_J, "j")
    _key(ed, Qt.Key.Key_Return)
    assert ed._rendered.document().toPlainText() == before
