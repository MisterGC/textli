"""Read-view link following: .md opens in place with gb/Backspace back-nav,
.grafli shows a stay-tuned notice, other resources go to the system handler,
dead links flash instead of creating files, and `gl` lists/follows links."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QTextCursor  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli.editor import ZenMarkdownEditor  # noqa: E402


def _make_docs() -> Path:
    d = Path(tempfile.mkdtemp(prefix="textli_links_"))
    (d / "a.md").write_text(
        "# Alpha\n\n"
        "Go to [beta](b.md), [beta bit](b.md#the-bit), "
        "[diagram](chart.grafli), [page](page.html), [dead](missing.md).\n")
    (d / "b.md").write_text("# Beta\n\nbody\n\n## The bit\n\ndetail here\n")
    (d / "page.html").write_text("<h1>hi</h1>")
    return d


def _open(main: Path) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(900, 640)
    ed = ZenMarkdownEditor(parent, main.read_text(), title="t", file_path=main)
    ed._parent = parent
    ed._toggle_rendered()
    return ed


def _caret_on(ed, href_contains: str):
    doc = ed._rendered.document()
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            href = frag.charFormat().anchorHref()
            if href and href_contains in href:
                cur = ed._rendered.textCursor()
                cur.setPosition(frag.position())
                ed._rendered.setTextCursor(cur)
                return href
            it += 1
        block = block.next()
    raise AssertionError(f"no link containing {href_contains!r}")


def test_follow_md_link_opens_in_place_and_back_returns():
    d = _make_docs()
    ed = _open(d / "a.md")
    href = _caret_on(ed, "b.md")
    ed._follow_rendered_link(href)
    assert ed._file_path == d / "b.md"
    assert "Beta" in ed._rendered.toPlainText()
    assert len(ed._nav_stack) == 1
    # gb walks back to where we were
    ed._navigate_back()
    assert ed._file_path == d / "a.md"
    assert ed._nav_stack == []


def test_md_link_fragment_jumps_to_heading():
    d = _make_docs()
    ed = _open(d / "a.md")
    ed._follow_rendered_link("b.md#the-bit")
    assert ed._file_path == d / "b.md"
    # caret landed on the "The bit" heading, not the document top
    block = ed._rendered.textCursor().block()
    assert block.text().strip() == "The bit"


def test_grafli_link_shows_stay_tuned_and_does_not_navigate():
    d = _make_docs()
    ed = _open(d / "a.md")
    ed._follow_rendered_link("chart.grafli")
    assert "stay tuned" in ed._last_notice
    assert ed._file_path == d / "a.md"       # stayed put
    assert ed._nav_stack == []


def test_missing_md_link_flashes_and_creates_nothing():
    d = _make_docs()
    ed = _open(d / "a.md")
    ed._follow_rendered_link("missing.md")
    assert "not found" in ed._last_notice
    assert ed._file_path == d / "a.md"
    assert not (d / "missing.md").exists()   # unlike `go`, no create-on-open


def test_other_resource_opens_with_system_handler():
    d = _make_docs()
    ed = _open(d / "a.md")
    opened = []
    ed._open_external = lambda url: opened.append(url)
    ed._follow_rendered_link("page.html")
    assert len(opened) == 1
    assert opened[0].toLocalFile() == str(d / "page.html")
    assert ed._file_path == d / "a.md"       # external, no in-app navigation


def test_web_link_still_opens_externally():
    d = _make_docs()
    ed = _open(d / "a.md")
    opened = []
    ed._open_external = lambda url: opened.append(url)
    assert ed._follow_rendered_link("https://example.com") is True
    assert opened and opened[0].toString() == "https://example.com"


def test_back_at_root_is_a_noop_with_notice():
    d = _make_docs()
    ed = _open(d / "a.md")
    ed._navigate_back()
    assert "no page to go back" in ed._last_notice
    assert ed._file_path == d / "a.md"


def test_links_overview_lists_every_link_and_follows_on_enter():
    d = _make_docs()
    ed = _open(d / "a.md")
    ed._open_links_overview()
    assert ed._overview_overlay is not None
    # five links in a.md, targets aligned with rows
    assert len(ed._overview_rows) == 5
    assert ed._overview_targets and len(ed._overview_targets) == 5
    # pick the row whose target is the plain b.md link and press Enter
    idx = next(i for i, t in enumerate(ed._overview_targets) if t == "b.md")
    ed._jump_to_overview_row(idx)
    assert ed._overview_overlay is None       # overview closed
    assert ed._file_path == d / "b.md"        # and the link was followed


def test_whisper_shows_link_target_when_caret_on_link():
    d = _make_docs()
    ed = _open(d / "a.md")
    _caret_on(ed, "b.md")
    ed._refresh_status()
    assert ed._status_label.text().startswith("→ b.md")
    # off the link, the breadcrumb returns
    cur = ed._rendered.textCursor()
    cur.movePosition(QTextCursor.MoveOperation.Start)
    ed._rendered.setTextCursor(cur)
    ed._refresh_status()
    assert "→" not in ed._status_label.text()


def test_write_mode_enter_does_not_navigate_to_files():
    d = _make_docs()
    ed = _open(d / "a.md")
    ed._toggle_rendered()                      # back to the write view
    # the shared write-view follow handles web/#heading only
    assert ed._follow_link("b.md") is False
    assert ed._file_path == d / "a.md"
