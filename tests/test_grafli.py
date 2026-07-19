"""`.grafli` image refs in the read view (#42): an `![](file.grafli)` image ref
renders inline as the diagram grafli's ``render`` CLI produces. Covers CLI
discovery, invocation args, the render cache and its mtime invalidation, the
graceful fallbacks (absent CLI, a failing CLI, a hanging CLI), coexistence with
a CriticMarkup comment, and that a `.grafli` *link* keeps its old notice.

The real grafli CLI is never required: a tiny fake executable on a prepended
``PATH`` emulates ``grafli render in out --width N`` by copying a template PNG
and logging each invocation, so discovery/args/caching/fallbacks are all
exercised without it."""

from __future__ import annotations

import os
import stat
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli import graflirender  # noqa: E402
from textli.editor import ZenMarkdownEditor, _GRAFLI_SCHEME  # noqa: E402
from textli.fonts import register_bundled_fonts  # noqa: E402


# ── fake grafli CLI ──────────────────────────────────────────────────────

# `render <input> <output> --width <N>`: copy the template PNG to <output> and
# append the args to a log, unless a mode env var asks it to fail or hang.
_FAKE = """\
#!{python}
import os, shutil, sys
args = sys.argv[1:]
log = os.environ.get("FAKE_GRAFLI_LOG")
if log:
    with open(log, "a") as fh:
        fh.write(" ".join(args) + "\\n")
mode = os.environ.get("FAKE_GRAFLI_MODE", "ok")
if mode == "fail":
    sys.stderr.write("boom\\n")
    sys.exit(1)
if mode == "hang":
    import time
    time.sleep(30)
shutil.copyfile(os.environ["FAKE_GRAFLI_TEMPLATE"], args[2])
sys.exit(0)
"""


@pytest.fixture(autouse=True)
def _clear_cache():
    graflirender._cache.clear()
    yield
    graflirender._cache.clear()


@pytest.fixture
def template(tmp_path) -> Path:
    QApplication.instance() or QApplication([])
    img = QImage(64, 48, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.blue)
    path = tmp_path / "template.png"
    assert img.save(str(path), "PNG")
    return path


@pytest.fixture
def fake_grafli(tmp_path, template, monkeypatch) -> Path:
    """Install the fake CLI on a prepended PATH; return the invocation log."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "grafli"
    script.write_text(_FAKE.format(python=sys.executable))
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    log = tmp_path / "invocations.log"
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_GRAFLI_TEMPLATE", str(template))
    monkeypatch.setenv("FAKE_GRAFLI_LOG", str(log))
    return log


@pytest.fixture
def no_grafli(tmp_path, monkeypatch) -> None:
    """A PATH with no grafli on it — the absent-CLI case."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))


# ── helpers ──────────────────────────────────────────────────────────────

def _doc_with(tmp_path: Path, body: str) -> Path:
    (tmp_path / "diagram.grafli").write_text("box A\n")
    md = tmp_path / "doc.md"
    md.write_text(body)
    return md


def _editor(md_path: Path) -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    register_bundled_fonts()
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, md_path.read_text(), title="d",
                           file_path=md_path)
    ed._parent = parent
    ed._suggest_animate = False
    return ed


def _grafli_images(ed) -> list[str]:
    doc = ed._rendered.document()
    names = []
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            cf = it.fragment().charFormat()
            if cf.isImageFormat():
                name = cf.toImageFormat().name()
                if name.startswith(f"{_GRAFLI_SCHEME}://"):
                    names.append(name)
            it += 1
        block = block.next()
    return names


# ── graflirender: pure ref finding (no Qt, no CLI) ───────────────────────

def test_find_image_refs_picks_grafli_images_only():
    md = ("![](a.grafli) and [a link](b.grafli) and ![](c.png) "
          "and ![alt](sub/d.GRAFLI)")
    refs = graflirender.find_image_refs(md, [])
    assert [src for _, _, src in refs] == ["a.grafli", "sub/d.GRAFLI"]


def test_find_image_refs_skips_code_regions():
    md = "![](x.grafli)\n"
    # the whole string marked as code → no ref
    assert graflirender.find_image_refs(md, [(0, len(md))]) == []


# ── editor integration via the fake CLI ──────────────────────────────────

def test_grafli_image_renders_when_cli_present(tmp_path, fake_grafli):
    md = _doc_with(tmp_path, "Intro.\n\n![](diagram.grafli)\n\nOutro.\n")
    ed = _editor(md)
    ed._toggle_rendered()
    assert _grafli_images(ed)                         # a diagram image landed
    args = fake_grafli.read_text().split()
    assert args[0] == "render"
    assert args[1].endswith("diagram.grafli")
    assert "--width" in args and int(args[args.index("--width") + 1]) > 0


def test_absent_cli_falls_back_without_crash(tmp_path, no_grafli):
    md = _doc_with(tmp_path, "Intro.\n\n![](diagram.grafli)\n\nOutro.\n")
    ed = _editor(md)
    ed._toggle_rendered()
    assert _grafli_images(ed) == []                   # no diagram resource
    assert "Outro." in ed._rendered.document().toPlainText()   # page still renders


def test_failing_cli_falls_back(tmp_path, fake_grafli, monkeypatch):
    monkeypatch.setenv("FAKE_GRAFLI_MODE", "fail")
    md = _doc_with(tmp_path, "Intro.\n\n![](diagram.grafli)\n\nOutro.\n")
    ed = _editor(md)
    ed._toggle_rendered()
    assert _grafli_images(ed) == []
    assert "Outro." in ed._rendered.document().toPlainText()


def test_hanging_cli_times_out_and_falls_back(tmp_path, fake_grafli, monkeypatch):
    monkeypatch.setenv("FAKE_GRAFLI_MODE", "hang")
    (tmp_path / "d.grafli").write_text("box A\n")
    rendered = graflirender.render(tmp_path / "d.grafli", width_px=600, dpr=1.0,
                                   timeout=0.3)
    assert rendered is None                           # killed at the timeout


def test_render_is_cached_and_mtime_invalidates(tmp_path, fake_grafli):
    md = _doc_with(tmp_path, "Intro.\n\n![](diagram.grafli)\n\nOutro.\n")
    ed = _editor(md)
    ed._toggle_rendered()
    ed._render_markdown(ed._editor.toPlainText())     # second render, unchanged
    assert len(fake_grafli.read_text().splitlines()) == 1   # CLI invoked once
    # touch the .grafli file's mtime → the next render re-invokes
    src = tmp_path / "diagram.grafli"
    os.utime(src, (time.time() + 5, time.time() + 5))
    ed._render_markdown(ed._editor.toPlainText())
    assert len(fake_grafli.read_text().splitlines()) == 2


def test_comment_near_grafli_image_stays_intact(tmp_path, fake_grafli):
    md = _doc_with(
        tmp_path,
        "![](diagram.grafli)\n\nA {==commented word==}{>>a note<<} nearby.\n")
    ed = _editor(md)
    ed._toggle_rendered()
    assert _grafli_images(ed)                          # the diagram rendered
    assert len(ed._rendered_comments) == 1             # the comment survived
    _s, _e, comment = ed._rendered_comments[0]
    assert comment.span == "commented word"


def test_grafli_link_is_untouched_by_the_image_feature(tmp_path, fake_grafli):
    # A link (not an image ref) never renders a diagram — it keeps the notice.
    md = _doc_with(tmp_path, "See [the diagram](diagram.grafli) for details.\n")
    ed = _editor(md)
    ed._toggle_rendered()
    assert _grafli_images(ed) == []                    # no image, it's a link
    ed._follow_rendered_link("diagram.grafli")
    assert "stay tuned" in ed._last_notice             # old behavior intact
