"""Paper surface: the procedural grain tile and light falloff (paper.py),
the ⌘⇧P toggle, and its persistence."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from textli import paper  # noqa: E402
from textli import settings as md_settings  # noqa: E402
from textli.constants import (  # noqa: E402
    _CTRL_MOD,
    ZEN_MD_BG,
    ZEN_MD_PAPER_GRAIN,
    ZEN_MD_PAPER_TILE,
)
from textli.editor import ZenMarkdownEditor  # noqa: E402

MD = "# Heading\n\nSome prose to paint under.\n"

SHIFT_CTRL = _CTRL_MOD | Qt.KeyboardModifier.ShiftModifier


def _editor() -> ZenMarkdownEditor:
    QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(1000, 700)
    ed = ZenMarkdownEditor(parent, MD, title="T")
    ed._parent = parent  # keep a ref alive
    return ed


def _press(ed, key, mod=Qt.KeyboardModifier.NoModifier):
    return ed._handle_key(QKeyEvent(QEvent.Type.KeyPress, key, mod))


def test_grain_tile_matches_dpr_and_is_cached():
    QApplication.instance() or QApplication([])
    tile = paper.grain_tile(2.0)
    assert tile.width() == tile.height() == ZEN_MD_PAPER_TILE * 2
    assert tile.devicePixelRatio() == 2.0
    assert paper.grain_tile(2.0) is tile      # built once per ratio


def test_grain_is_deterministic_noise_within_amplitude():
    QApplication.instance() or QApplication([])
    img = paper._build_tile(ZEN_MD_BG, 1.0)
    assert img == paper._build_tile(ZEN_MD_BG, 1.0)   # fixed seed — same sheet
    base = (ZEN_MD_BG.red(), ZEN_MD_BG.green(), ZEN_MD_BG.blue())
    shades = set()
    for y in range(0, img.height(), 5):
        for x in range(0, img.width(), 5):
            px = img.pixelColor(x, y)
            got = (px.red(), px.green(), px.blue())
            shades.add(got)
            for channel, want in zip(got, base):
                assert abs(channel - want) <= ZEN_MD_PAPER_GRAIN
    assert len(shades) > 1                    # actual noise, not a flat fill


def test_paper_defaults_on_and_dresses_both_views():
    ed = _editor()
    assert ed._paper is True
    assert ed._editor._paper is True
    assert ed._rendered._paper is True


def test_paper_toggle_key_flips_views_and_persists():
    # ⌘⇧P must be routed before plain ⌘P — if print ever swallowed it, this
    # test would hang on the modal print dialog rather than merely fail.
    ed = _editor()
    assert _press(ed, Qt.Key.Key_P, SHIFT_CTRL)
    assert ed._paper is False
    assert ed._editor._paper is False and ed._rendered._paper is False
    assert md_settings.app_settings().value(
        "zen_md/paper", True, type=bool) is False
    assert ed._mode_flash.text() == "PAPER OFF"
    assert _press(ed, Qt.Key.Key_P, SHIFT_CTRL)
    assert ed._paper is True
    assert ed._editor._paper is True and ed._rendered._paper is True
    assert ed._mode_flash.text() == "PAPER"


def test_paper_pref_restores_off_in_the_next_editor():
    ed = _editor()
    _press(ed, Qt.Key.Key_P, SHIFT_CTRL)      # off, persisted
    ed2 = _editor()
    assert ed2._paper is False
    assert ed2._editor._paper is False and ed2._rendered._paper is False
    ed2._toggle_paper()                       # leave the shared pref on again
    assert ed2._paper is True


def test_bare_view_paper_falls_back_to_viewport_frame():
    # A view without an editor parent has no card to frame the light — the
    # falloff spans its own viewport instead of raising.
    from textli.editor import _ReadingView
    QApplication.instance() or QApplication([])
    view = _ReadingView()
    view.resize(300, 200)
    assert not view.grab().isNull()


def test_paint_smoke_both_views_and_both_states():
    # Executes the real paint path (tile + gradient) headless in every
    # combination — a paint-time error raises instead of drawing wrong.
    ed = _editor()
    assert not ed.grab().isNull()             # editor chrome (paint_card)
    assert not ed._editor.grab().isNull()     # write view, paper on
    ed._toggle_rendered()
    assert not ed._rendered.grab().isNull()   # read view, paper on
    ed._toggle_paper()
    assert not ed._rendered.grab().isNull()   # read view, flat page
    ed._toggle_rendered()
    assert not ed._editor.grab().isNull()     # write view, flat page
    ed._toggle_paper()                        # restore the shared pref
