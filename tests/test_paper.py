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
    _CTRL_MOD, ZEN_MD_DESK_GRAIN, ZEN_MD_PAPER_GRAIN, ZEN_MD_PAPER_TILE,
)
from textli.editor import ZenMarkdownEditor  # noqa: E402
from textli import theme

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
    img = paper._build_tile(theme.ZEN_MD_BG, 1.0)
    assert img == paper._build_tile(theme.ZEN_MD_BG, 1.0)   # fixed seed — same sheet
    base = (theme.ZEN_MD_BG.red(), theme.ZEN_MD_BG.green(), theme.ZEN_MD_BG.blue())
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


# ── the desk: the surround as a surface (#56) ──

def _desked(canvas_w: int = 0):
    """An editor painted at full opacity in a 1400x800 host, plus a sampler.

    The fade-in leaves the widget at opacity 0, which paints nothing at all —
    so a grab straight after construction would measure the host, not the desk.
    """
    QApplication.instance() or QApplication([])
    host = QWidget()
    host.resize(1400, 800)
    pal = host.palette()
    pal.setColor(pal.ColorRole.Window, theme.ZEN_BACKDROP)
    host.setPalette(pal)
    host.setAutoFillBackground(True)
    canvas = None
    if canvas_w:
        canvas = QWidget(host)
        canvas.setGeometry(0, 0, canvas_w, 800)
        canvas.setAutoFillBackground(True)
    ed = ZenMarkdownEditor(host, MD, title="T", canvas=canvas)
    ed.resize(1400, 800)
    host.show()
    ed._opacity.setOpacity(1.0)
    ed._host = host      # keep refs alive
    ed._cv = canvas

    def band(x0, width):
        """(mean lightness, spread) of a horizontal run at the card's midline."""
        img = host.grab().toImage()
        y = int(ed._card_rect().center().y())
        vals = [img.pixelColor(x, y).lightness() for x in range(x0, x0 + width)]
        return sum(vals) / len(vals), max(vals) - min(vals)

    return ed, band


def test_desk_tile_matches_dpr_and_is_cached():
    QApplication.instance() or QApplication([])
    tile = paper.desk_tile(2.0)
    assert tile.width() == tile.height() == ZEN_MD_PAPER_TILE * 2
    assert tile.devicePixelRatio() == 2.0
    assert paper.desk_tile(2.0) is tile


def test_desk_grain_is_translucent_and_bakes_no_colour():
    """The sheet's tile bakes the page colour and so must be keyed by it
    (#49). The desk's cannot: an embedding host paints the ground under the
    chrome. It modulates alpha over white instead — which also means it can
    never go stale against a palette switch."""
    QApplication.instance() or QApplication([])
    img = paper._build_desk_tile(1.0)
    assert img.hasAlphaChannel()
    alphas = set()
    for y in range(0, img.height(), 5):
        for x in range(0, img.width(), 5):
            px = img.pixelColor(x, y)
            assert (px.red(), px.green(), px.blue()) == (255, 255, 255)
            assert 0 <= px.alpha() <= ZEN_MD_DESK_GRAIN
            alphas.add(px.alpha())
    assert len(alphas) > 1                       # noise, not a flat wash

    theme.set_theme("dark")
    try:                                         # same tile in either palette
        assert paper._build_desk_tile(1.0) == img
    finally:
        theme.set_theme("light")


def test_the_desk_gives_the_surround_texture():
    ed, band = _desked()
    _, spread = band(3, 40)
    assert spread > 0                            # grain
    ed._paper = False
    ed.update()
    _, flat = band(3, 40)
    assert flat == 0                             # the toggle takes it away


def test_the_desk_sinks_toward_the_window_edges():
    """One light: the sheet's own falloff runs bright-centre to dark-edge, and
    the desk has to run the same way. It shades toward black rather than the
    sheet's warm body ink — body ink is *lighter* than the dimmed surround, so
    reusing it brightened the corners instead of sinking them."""
    for name in ("light", "dark"):
        theme.set_theme(name)
        try:
            ed, band = _desked()
            edge, _ = band(3, 40)
            beside, _ = band(int(ed._card_rect().left()) - 44, 40)
            assert edge < beside, f"{name}: corners must sit deeper than the sheet's edge"
        finally:
            theme.set_theme("light")


def test_the_desk_leaves_a_host_canvas_alone():
    """A host's canvas keeps its own pixels under the gentler wash — the desk
    is chrome-only, or an embedded textli would paint over its host."""
    ed, band = _desked(canvas_w=300)
    _, on_canvas = band(60, 180)
    assert on_canvas == 0
    _, on_chrome = band(int(ed._card_rect().right()) + 20, 40)
    assert on_chrome > 0


def test_the_grain_tile_never_outlives_its_palette():
    """#49 — the tile bakes the page colour into its colour table, so keying
    it on the device-pixel-ratio alone let a dark tile paint under light ink
    the next time an editor opened. No editor is involved here on purpose:
    the switch happens with nothing listening, which is exactly the case an
    invalidate-on-apply_theme hook could not cover."""
    QApplication.instance() or QApplication([])
    theme.set_theme("dark")
    dark_tile = paper.grain_tile(2.0)
    dark_px = dark_tile.toImage().pixelColor(0, 0)

    theme.set_theme("light")
    light_px = paper.grain_tile(2.0).toImage().pixelColor(0, 0)
    assert light_px != dark_px
    # the grain sits within a few luminance steps of its own page colour
    assert abs(light_px.red() - theme.LIGHT.ZEN_MD_BG.red()) <= 4

    # switching back reuses the tile already built for that palette
    theme.set_theme("dark")
    assert paper.grain_tile(2.0) is dark_tile
    theme.set_theme("light")
