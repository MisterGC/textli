# Embedding

textli's editor is a plain PySide6 widget — the standalone app is just a
thin host window around it. Two widgets are exported:

## `ZenMarkdownEditor` — the full editor

The complete writing + reading + review surface. Parent it into any widget;
it fills the parent, paints its translucent dim wash over the parent's
content, and sizes its centered card itself.

```python
from pathlib import Path
from textli import ZenMarkdownEditor
from textli.fonts import register_bundled_fonts

register_bundled_fonts()          # once, after QApplication exists

editor = ZenMarkdownEditor(
    parent=host_widget,           # fills this widget
    text=Path("notes.md").read_text(),
    title="notes.md",
    file_path=Path("notes.md"),   # enables autosave; omit for buffer editing
    anchor="",                    # optional heading slug to scroll to
    start_in_read=False,          # True → open in the reading view
    canvas=None,                  # optional: a widget rect the dim wash skips
)
editor.finished.connect(lambda text: ...)   # Esc — final text
editor.cancelled.connect(lambda: ...)       # ⇧Esc — discarded
editor.file_saved.connect(lambda path: ...) # each autosave
```

Signals:

- `finished(str)` — the editor closed normally; carries the final text.
- `cancelled()` — the session was discarded.
- `file_saved(Path)` — emitted on every autosave when file-backed.

The `canvas` parameter is for hosts that want part of their UI to stay
fully saturated while the editor dims the rest — grafli passes its diagram
canvas here.

The editor owns its own F1 help (`textli.editor_help_html()` returns the
HTML), so embedded and standalone use show identical documentation.

## `InlineVimEditor` — one field, vim keys

A small `QPlainTextEdit` with the same vim keybindings, minus the
full-screen chrome, file I/O, and overlays — meant for editing a single
piece of text in place (grafli uses it on canvas notes via a
`QGraphicsProxyWidget`).

```python
from textli import InlineVimEditor

field = InlineVimEditor(
    text="initial text",
    markdown=True,                # optional Markdown highlighting
    commit_on_focus_out=True,     # losing focus commits (default)
    max_lines=24,
)
field.committed.connect(lambda text: ...)   # Esc in NORMAL mode
field.cancelled.connect(lambda: ...)        # ⇧Esc
```

It opens in INSERT mode so quick edits feel like a plain text box; vim
power is one `Esc` away.
