"""Procedural paper surface — grain and light painted under the editor views.

A flat hex over two million pixels reads as a void, not a page. Two
whisper-level cues give the surface material without giving the eye anything
to look *at* — both tuned to sit below conscious notice (texture felt, not
seen), so the zen stays intact:

- **Grain** — fine luminance noise around the page color. Noise is
  pattern-free, so a scroll blit can never produce a visible seam, and the
  fixed seed means the sheet looks the same every launch. The tile is built
  at the view's device-pixel-ratio so grain stays crisp on high-DPI panels.
- **Light** — a horizontal falloff, fully bright across the central reading
  plateau and a few percent darker (in warm body ink, not gray) toward the
  window edges. Horizontal *only* on purpose: its value depends on x alone,
  so vertical scroll blits shift it onto itself and never smear it.

The sheet is painted twice per frame and must read as one material: the
editor fills its rounded card (``paint_card``) behind the chrome, and each
view paints its own patch (``paint``) at the top of ``paintEvent`` — over
the opaque stylesheet base, under the text — passing the card as the light
frame so the falloff runs across the whole sheet without a seam at the view
edge. Grain tiles anchor locally (card vs. viewport coordinates): the
offset depends only on the paint rect, so partial repaints (caret blinks,
single-line updates) reproduce the exact pixels they cover, and the
mismatch where card meets view is invisible — misaligned noise is noise.

The surround gets the same two cues (``paint_desk``, #56), so the sheet
lies on a desk rather than floating in a void. It is the same surface in a
darker key, and it differs in exactly the two places a dark ground forces:
its grain is a *translucent* overlay, because an embedding host paints the
ground and the desk cannot bake a colour it does not know; and its falloff
shades toward black rather than the sheet's warm body ink, which is lighter
than the dimmed surround and would brighten the corners it is meant to
sink. The light is one light — the desk's frame is centred on the card but
spans the window, so the ramp continues past the sheet instead of ending
with it.
"""

from __future__ import annotations

import random

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    qRgb,
    qRgba,
)
from PySide6.QtWidgets import QAbstractScrollArea

from textli.constants import (
    ZEN_MD_DESK_EDGE_ALPHA, ZEN_MD_DESK_GRAIN,
    ZEN_MD_PAPER_EDGE_ALPHA, ZEN_MD_PAPER_GRAIN, ZEN_MD_PAPER_PLATEAU,
    ZEN_MD_PAPER_SEED, ZEN_MD_PAPER_TILE,
)
from textli import theme

# One tile per (device-pixel-ratio in hundredths, page colour). The colour
# belongs in the key because the tile *bakes* it into its colour table: keyed
# on the ratio alone, a tile outlives the palette it was built for and the
# next view paints the old theme's grain under the new theme's ink (#49).
# Keying on the value it depends on also means nothing has to remember to
# invalidate — a switch simply misses, and both palettes stay cached.
_tiles: dict[tuple[int, str], QPixmap] = {}

# The desk's tiles need no colour in the key: they bake none (#56).
_desk_tiles: dict[int, QPixmap] = {}


def _build_tile(base: QColor, dpr: float) -> QImage:
    """One grain tile: uniform noise of ±ZEN_MD_PAPER_GRAIN luminance steps
    around ``base`` at device resolution. Indexed8 keeps it loop-free — the
    seeded random bytes *are* the pixels, the color table maps byte → shade."""
    side = max(1, round(ZEN_MD_PAPER_TILE * dpr))
    data = random.Random(ZEN_MD_PAPER_SEED).randbytes(side * side)
    img = QImage(data, side, side, side, QImage.Format.Format_Indexed8)
    span = 2 * ZEN_MD_PAPER_GRAIN + 1
    img.setColorTable([
        qRgb(*(min(255, max(0, c + b % span - ZEN_MD_PAPER_GRAIN))
               for c in (base.red(), base.green(), base.blue())))
        for b in range(256)
    ])
    return img.copy()   # detach from `data` before it goes out of scope


def _build_desk_tile(dpr: float) -> QImage:
    """One desk tile: translucent white noise, alpha 0..ZEN_MD_DESK_GRAIN.

    Unlike the sheet's tile this bakes no colour. An embedded host paints the
    ground under the chrome, so the desk cannot know what it sits on and has
    to modulate whatever is already there — which also means it can never go
    stale against a palette switch. Same Indexed8 trick, alpha in the colour
    table instead of a shade: the seeded bytes *are* the pixels.

    It only ever lightens. At these alphas, blending a near-black backdrop
    toward white moves it some six times as far as blending toward black, so
    a symmetric tile would read one-directional anyway.
    """
    side = max(1, round(ZEN_MD_PAPER_TILE * dpr))
    data = random.Random(ZEN_MD_PAPER_SEED).randbytes(side * side)
    img = QImage(data, side, side, side, QImage.Format.Format_Indexed8)
    span = ZEN_MD_DESK_GRAIN + 1
    img.setColorTable([qRgba(255, 255, 255, b % span) for b in range(256)])
    return img.copy()   # detach from `data` before it goes out of scope


def invalidate_cache() -> None:
    """Drop every cached tile, sheet and desk.

    Not needed for a palette switch — the sheet's cache is keyed by page
    colour and the desk's tiles bake no colour at all, so that takes care of
    itself. This is the reset for the cases the keys can't see, such as the
    grain constants changing under a test.
    """
    _tiles.clear()
    _desk_tiles.clear()


def desk_tile(dpr: float) -> QPixmap:
    """The desk tile for a device-pixel-ratio, built once and cached."""
    key = round(dpr * 100)
    tile = _desk_tiles.get(key)
    if tile is None:
        tile = QPixmap.fromImage(_build_desk_tile(dpr))
        tile.setDevicePixelRatio(dpr)
        _desk_tiles[key] = tile
    return tile


def grain_tile(dpr: float) -> QPixmap:
    """The grain tile for a device-pixel-ratio, built once per palette and
    cached."""
    base = theme.ZEN_MD_BG
    key = (round(dpr * 100), base.name())
    tile = _tiles.get(key)
    if tile is None:
        tile = QPixmap.fromImage(_build_tile(base, dpr))
        tile.setDevicePixelRatio(dpr)
        _tiles[key] = tile
    return tile


def _paint_light(painter: QPainter, rect, x0: float, w: float,
                 edge_alpha: int = ZEN_MD_PAPER_EDGE_ALPHA,
                 ink: QColor | None = None) -> None:
    """The falloff: ``ink`` ramping in from both ends of the light frame
    ``[x0, x0 + w]``, fully clear across the central plateau.

    The sheet shades toward warm body ink, which is darker than paper. The
    desk cannot reuse it: body ink is *lighter* than the dimmed surround, so
    the same gradient brightens the corners instead of sinking them. Shadow
    is whatever is darker than the ground, so the desk passes black (#56).
    """
    ink = QColor(theme.ZEN_TEXT_COLOR if ink is None else ink)
    grad = QLinearGradient(x0, 0.0, x0 + w, 0.0)
    edge = (1.0 - ZEN_MD_PAPER_PLATEAU) / 2.0   # where falloff meets full bright
    for pos, alpha in (
            (0.0, edge_alpha),
            (edge * 0.5, edge_alpha // 4),   # eased knee
            (edge, 0),
            (1.0 - edge, 0),
            (1.0 - edge * 0.5, edge_alpha // 4),
            (1.0, edge_alpha)):
        ink.setAlpha(alpha)
        grad.setColorAt(pos, QColor(ink))
    painter.fillRect(rect, QBrush(grad))


def paint(view: QAbstractScrollArea, rect: QRect,
          light_x: float | None = None, light_w: float | None = None) -> None:
    """Paint the paper surface across ``rect`` (the paint-event rect) of a
    view's viewport. Call first thing in ``paintEvent`` so text lands on top.
    ``light_x``/``light_w`` frame the falloff in viewport coordinates —
    pass the enclosing card so the light is continuous with the chrome's;
    default is the viewport itself (standalone views)."""
    vp = view.viewport()
    painter = QPainter(vp)
    tile = grain_tile(vp.devicePixelRatioF())
    t = ZEN_MD_PAPER_TILE
    painter.drawTiledPixmap(QRectF(rect), tile,
                            QPointF(rect.x() % t, rect.y() % t))
    if light_x is None or light_w is None:
        light_x, light_w = 0.0, float(vp.width())
    _paint_light(painter, rect, light_x, light_w)
    painter.end()


def paint_card(painter: QPainter, card: QRectF, radius: float,
               dpr: float) -> None:
    """Dress the editor's rounded card in the paper surface — grain and
    light clipped to the card, over its base fill. The views inside then
    paint their own patches with this card as light frame, so the whole
    sheet reads as one material."""
    painter.save()
    path = QPainterPath()
    path.addRoundedRect(card, radius, radius)
    painter.setClipPath(path)
    tile = grain_tile(dpr)
    t = ZEN_MD_PAPER_TILE
    painter.drawTiledPixmap(card, tile,
                            QPointF(card.x() % t, card.y() % t))
    _paint_light(painter, card, card.x(), card.width())
    painter.restore()


def paint_desk(painter: QPainter, rect: QRectF, light_x: float,
               light_w: float, dpr: float) -> None:
    """Dress the surround in the desk surface — translucent grain and a
    deeper falloff, laid over whatever the chrome wash left (#56).

    ``light_x``/``light_w`` frame the falloff. The caller passes a frame
    centred on the *card* but as wide as the window, so the sheet and the
    desk are lit from the same place while the desk keeps falling off past
    the sheet into the corners.

    The caller owns the clip — a host's canvas is off limits — and this
    paints across the whole ``rect`` inside it, so the tiling phase stays
    continuous and the chrome strips read as one surface rather than four.
    """
    tile = desk_tile(dpr)
    t = ZEN_MD_PAPER_TILE
    painter.drawTiledPixmap(rect, tile,
                            QPointF(rect.x() % t, rect.y() % t))
    _paint_light(painter, rect, light_x, light_w, ZEN_MD_DESK_EDGE_ALPHA,
                 QColor(0, 0, 0))
