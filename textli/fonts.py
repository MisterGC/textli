"""Bundled-font registration for textli.

Ships JetBrains Mono Nerd Font (the editor face) and Caveat (the handwriting
face used for comment annotations) so the editor renders identically
everywhere, whether run standalone or embedded in a host application.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

_BUNDLED_FONTS = (
    "JetBrainsMonoNerdFont-Regular.ttf",
    "JetBrainsMonoNerdFont-Bold.ttf",
    "Caveat.ttf",
    "Literata-Regular.ttf",
    "Literata-Bold.ttf",
)

_registered = False


def register_bundled_fonts() -> None:
    """Load the fonts shipped in textli/fonts/ into the running QApplication.

    Idempotent: the public editor widgets call this on construction so an
    embedding host gets the bundled faces with no extra wiring, and the
    standalone entry point still calls it too — the guard keeps repeated calls
    (and duplicate font entries) harmless."""
    global _registered
    if _registered:
        return
    fonts_dir = Path(__file__).parent / "fonts"
    for name in _BUNDLED_FONTS:
        path = fonts_dir / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
    _registered = True
