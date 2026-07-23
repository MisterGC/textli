"""`.grafli` diagram rendering for the read view (#42).

textli and [grafli](https://github.com/MisterGC/grafli) share one stable
contract — grafli's ``render`` CLI — and nothing else: no import, no
Python-level coupling. When the CLI is on ``PATH``, a Markdown image ref to a
``.grafli`` file (`![](architecture.grafli)`) shells out to
``grafli render <src> <out.png> --width <px>`` and the produced PNG is loaded
as a ``QImage`` for the reading view.

Every failure mode falls back silently to today's behavior — grafli absent, a
non-zero exit, a timeout, or a missing/blank output all yield ``None`` and the
image ref is left untouched (Qt then tries the path itself and shows nothing).
No dialog, no whisper: a diagram that can't render never breaks or blocks the
page.

Kept out of `editor.py` so the discovery, the subprocess, and the render cache
live in one place — the same shape as `mathrender.py` / `chartrender.py`. The
Qt wiring (rewriting the ref, attaching the resource) stays in the editor.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

from PySide6.QtGui import QImage

# The CLI textli invokes. Resolved against ``PATH`` on every render pass (not
# once per process), so installing grafli mid-session is picked up on the next
# re-render.
_CLI = "grafli"

# A render is bounded: the subprocess stall a page of diagrams can cost is at
# most this, once, thanks to the cache. A diagram that hangs is a broken
# diagram — let it time out and fall back rather than freeze the view.
_TIMEOUT_S = 5.0

# Sanity cap on the pixel width asked of grafli, so a wide column on a high-dpr
# display never demands an absurd raster. grafli preserves the aspect ratio.
_MAX_WIDTH_PX = 4096

# A Markdown image ref whose source is a ``.grafli`` file: `![alt](path.grafli)`,
# with an optional ``<…>`` wrap and an optional "title". Link refs (`[text](…)`)
# are deliberately not matched — v1 renders images only, links keep the
# stay-tuned notice.
_IMAGE_RE = re.compile(
    r"!\[[^\]]*\]\(\s*<?([^)>\s]+\.grafli)>?(?:\s+\"[^\"]*\")?\s*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RenderedDiagram:
    """A rasterized ``.grafli`` diagram — device-pixel-ratio scaled."""

    image: QImage


# (abspath, mtime, width_px, dpr) -> RenderedDiagram | None. Keyed on the source
# file's mtime so a re-render (zoom, view toggle, file-watch reload) re-invokes
# the CLI only when the diagram, or the target metrics, actually changed; a
# failed render caches its ``None`` too, so it doesn't re-shell on every pass.
_cache: dict[tuple, RenderedDiagram | None] = {}
_CACHE_MAX = 128


def available() -> bool:
    """True when the grafli CLI is on ``PATH``. Cheap enough to call once per
    render pass — the editor does, and skips the whole diagram pass when it's
    False, leaving every ``.grafli`` ref exactly as today."""
    return shutil.which(_CLI) is not None


def find_image_refs(md: str, code_ranges) -> list[tuple[int, int, str]]:
    """Every ``.grafli`` image ref in ``md`` as ``(start, end, src)``, skipping
    any that falls inside a Markdown code region (``code_ranges`` is a list of
    ``(start, end)`` spans, e.g. from :func:`comments.code_ranges`) — a ref in a
    fenced block or code span is documentation, not a directive, and stays
    literal. Pure text logic: no Qt, no subprocess."""
    def in_code(pos: int) -> bool:
        return any(a <= pos < b for a, b in code_ranges)

    return [(m.start(), m.end(), m.group(1))
            for m in _IMAGE_RE.finditer(md) if not in_code(m.start())]


def render(src, *, width_px: float, dpr: float,
           timeout: float = _TIMEOUT_S) -> RenderedDiagram | None:
    """Render the ``.grafli`` file ``src`` to a ``width_px`` pixel-wide PNG and
    load it as a ``QImage`` tagged at ``dpr``, or ``None`` on any failure
    (grafli absent, the file missing, a non-zero exit, a timeout, or a
    missing/blank output). Cached by absolute path + mtime + width + dpr, so a
    repeated render of an unchanged file is served without re-invoking the
    CLI."""
    if not available():
        return None
    try:
        abspath = os.path.abspath(os.fspath(src))
        mtime = os.path.getmtime(abspath)
    except OSError:
        return None
    w = max(1, min(int(round(width_px)), _MAX_WIDTH_PX))
    key = (abspath, mtime, w, round(float(dpr), 2))
    if key in _cache:
        return _cache[key]
    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    result = _render(abspath, w, dpr, timeout)
    _cache[key] = result
    return result


def _render(abspath: str, width_px: int, dpr: float,
            timeout: float) -> RenderedDiagram | None:
    # A per-process temp file, never next to the user's document. Loaded into
    # memory immediately, then unlinked — the cache holds the QImage, not the
    # file.
    fd, out = tempfile.mkstemp(suffix=".png", prefix="textli-grafli-")
    os.close(fd)
    try:
        try:
            proc = subprocess.run(
                [_CLI, "render", abspath, out, "--width", str(width_px)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=timeout)
        except (subprocess.TimeoutExpired, OSError):
            return None
        if proc.returncode != 0:
            return None
        if not os.path.exists(out) or os.path.getsize(out) == 0:
            return None
        image = QImage(out)
        if image.isNull():
            return None
        image.setDevicePixelRatio(float(dpr))
        return RenderedDiagram(image=image)
    finally:
        try:
            os.unlink(out)
        except OSError:
            pass
