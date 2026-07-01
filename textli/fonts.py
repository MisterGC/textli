"""Bundled-font registration for textli.

Ships JetBrains Mono Nerd Font so the editor renders identically everywhere,
whether run standalone or embedded in a host application.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

_BUNDLED_FONTS = (
    "JetBrainsMonoNerdFont-Regular.ttf",
    "JetBrainsMonoNerdFont-Bold.ttf",
)


def register_bundled_fonts() -> None:
    """Load the fonts shipped in textli/fonts/ into the running QApplication."""
    fonts_dir = Path(__file__).parent / "fonts"
    for name in _BUNDLED_FONTS:
        path = fonts_dir / name
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
