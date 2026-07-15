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
)
from PySide6.QtWidgets import QAbstractScrollArea

from textli.constants import (
    ZEN_MD_BG,
    ZEN_MD_PAPER_EDGE_ALPHA,
    ZEN_MD_PAPER_GRAIN,
    ZEN_MD_PAPER_PLATEAU,
    ZEN_MD_PAPER_SEED,
    ZEN_MD_PAPER_TILE,
    ZEN_TEXT_COLOR,
)

# One tile per device-pixel-ratio (keyed in hundredths); the page color is a
# constant, so the ratio is the only thing that varies between views.
_tiles: dict[int, QPixmap] = {}


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


def grain_tile(dpr: float) -> QPixmap:
    """The grain tile for a device-pixel-ratio, built once and cached."""
    key = round(dpr * 100)
    tile = _tiles.get(key)
    if tile is None:
        tile = QPixmap.fromImage(_build_tile(ZEN_MD_BG, dpr))
        tile.setDevicePixelRatio(dpr)
        _tiles[key] = tile
    return tile


def _paint_light(painter: QPainter, rect, x0: float, w: float) -> None:
    """The falloff: warm ink ramping in from both ends of the light frame
    ``[x0, x0 + w]``, fully clear across the central plateau."""
    ink = QColor(ZEN_TEXT_COLOR)
    grad = QLinearGradient(x0, 0.0, x0 + w, 0.0)
    edge = (1.0 - ZEN_MD_PAPER_PLATEAU) / 2.0   # where falloff meets full bright
    for pos, alpha in (
            (0.0, ZEN_MD_PAPER_EDGE_ALPHA),
            (edge * 0.5, ZEN_MD_PAPER_EDGE_ALPHA // 4),   # eased knee
            (edge, 0),
            (1.0 - edge, 0),
            (1.0 - edge * 0.5, ZEN_MD_PAPER_EDGE_ALPHA // 4),
            (1.0, ZEN_MD_PAPER_EDGE_ALPHA)):
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
