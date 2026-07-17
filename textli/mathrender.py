"""TeX → ``QImage`` rendering for the read view's math (`formulas.py`).

ziamath sets the TeX in STIX Two Math (bundled, OFL) and emits SVG; Qt's SVG
module rasterizes it at the view's device pixel ratio so formulas stay crisp
on retina displays. Glyphs are drawn in a caller-given ink color on a
transparent background, so a formula sits on the page — or on a comment
tint — like text does.

A formula ziamath can't parse renders as ``None``; the caller falls back to
showing the raw TeX (`formulas.code_span`) instead of breaking the page.

Kept out of `editor.py` so the ziamath specifics (SVG-Tiny compatibility,
baseline bookkeeping, the render cache) live in one place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import ziamath
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

# Qt SVG implements SVG Tiny 1.2 — without this ziamath emits SVG-2
# <symbol>/<use> glyph references that Qt silently drops (blank formulas).
ziamath.config.svg2 = False


@dataclass(frozen=True)
class RenderedFormula:
    """A rasterized formula plus the metrics the layout pass needs."""

    image: QImage       # device-pixel-ratio scaled, transparent background
    depth: float        # logical px the formula reaches below the baseline
    align_bottom: bool  # bottom-align the image (its math baseline then sits
                        # on/near the text baseline); False → center it


# (tex, display, px_size, color, dpr, descent) -> RenderedFormula | None.
# Re-renders are frequent (file watch, zoom, view toggles) and documents
# repeat their formulas across them, so a small cache pays for itself; parse
# failures are cached too, so a broken formula doesn't re-raise on every
# keystroke.
_cache: dict[tuple, RenderedFormula | None] = {}
_CACHE_MAX = 512


def render(tex: str, *, display: bool, px_size: float, color: str,
           dpr: float, descent: float = 0.0) -> RenderedFormula | None:
    """Rasterize ``tex`` at an em size of ``px_size`` logical pixels, or
    ``None`` when ziamath can't parse it. ``display`` picks display style
    (limits above/below) over text style (limits beside, for inline math).

    ``descent`` is the surrounding font's descent in logical px. Qt can place
    an inline image's bottom on the line bottom (baseline + descent) but can
    never hang it *below* that, so an inline formula whose depth fits inside
    the descent gets transparent bottom padding of ``descent - depth`` — with
    bottom alignment its math baseline then sits exactly on the text
    baseline. A slight overshoot (a subscript descender, up to 0.2 em) still
    bottom-aligns — the ~px error beats a visibly floating glyph. Only a
    genuinely deep formula (inline fraction, big operator) gives up on the
    baseline; the caller centers it instead (``align_bottom`` False)."""
    key = (tex, display, round(px_size, 2), color, round(dpr, 2),
           round(descent, 2))
    if key in _cache:
        return _cache[key]
    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    result = _render(tex, display, px_size, color, dpr, descent)
    _cache[key] = result
    return result


def _render(tex: str, display: bool, px_size: float, color: str,
            dpr: float, descent: float) -> RenderedFormula | None:
    try:
        expr = ziamath.Latex(tex, size=px_size, color=color,
                             inline=not display)
        svg = expr.svg()
        depth = max(0.0, -expr.getyofst())
    except Exception:
        return None
    renderer = QSvgRenderer(bytearray(svg, "utf-8"))
    size = renderer.defaultSize()
    if not renderer.isValid() or size.width() < 1 or size.height() < 1:
        return None
    # Sanity bound: ziamath occasionally explodes a stretchy delimiter (a
    # bare \lVert renders ~125 em tall). A formula that vast is a render
    # bug, not mathematics — fall back to raw TeX rather than letting one
    # glyph dwarf the page.
    if size.height() > 50 * px_size or size.width() > 200 * px_size:
        return None
    align_bottom = not display and depth <= descent + 0.2 * px_size
    pad = max(0.0, descent - depth) if align_bottom else 0.0
    image = QImage(math.ceil(size.width() * dpr),
                   math.ceil((size.height() + pad) * dpr),
                   QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size.width() * dpr,
                                    size.height() * dpr))
    painter.end()
    image.setDevicePixelRatio(dpr)
    return RenderedFormula(image=image, depth=depth,
                           align_bottom=align_bottom)
