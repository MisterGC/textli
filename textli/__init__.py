"""textli — a lightweight text editor with focused writing and reading in mind.

A full-window, iA Writer-inspired Markdown editor with vim keybindings, a
rendered reading view, and inline review (CriticMarkup comments and
track-changes suggestions). Run it standalone via the ``textli`` command, or
embed :class:`ZenMarkdownEditor` / :class:`InlineVimEditor` in any PySide6
application.
"""

from textli.editor import ZenMarkdownEditor, editor_help_html
from textli.inline_editor import InlineVimEditor

try:
    from textli._version import __version__
except ImportError:  # pragma: no cover — running from source without build metadata
    __version__ = "0.0.0"

__all__ = ["ZenMarkdownEditor", "InlineVimEditor", "editor_help_html", "__version__"]
