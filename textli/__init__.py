"""textli — a lightweight text editor with focused writing and reading in mind.

A full-window, distraction-free Markdown editor with vim keybindings, a
rendered reading view, and inline review (CriticMarkup comments and
track-changes suggestions). Run it standalone via the ``textli`` command, or
embed :class:`ZenMarkdownEditor` / :class:`InlineVimEditor` in any PySide6
application.

The editor ships two counterpart palettes. A host drives them on demand::

    import textli
    textli.set_theme("dark")          # or toggle_theme() / is_dark()

Open editors restyle themselves in place — they listen to
:data:`textli.theme_changed` — so a host only needs the call above. Construct
with ``theme="dark"`` to open on the dark ground without a flash of light.
"""

from textli.editor import ZenMarkdownEditor, editor_help_html
from textli.inline_editor import InlineVimEditor
from textli.theme import (
    is_dark, set_theme, toggle as toggle_theme, changed as theme_changed,
)

try:
    from textli._version import __version__
except ImportError:  # pragma: no cover — running from source without build metadata
    __version__ = "0.0.0"

__all__ = [
    "ZenMarkdownEditor", "InlineVimEditor", "editor_help_html",
    "set_theme", "toggle_theme", "is_dark", "theme_changed",
    "__version__",
]
