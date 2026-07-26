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

## Light and dark

The editor ships two counterpart palettes — warm paper, and the same warm
hue family on a low-key ground (`#1E1C19`, shared with
[grafli](https://github.com/MisterGC/grafli) so an embedded editor sits on
its host's board rather than glowing against it). Two palettes, not a theme
engine: there is no third theme and no settings surface.

A host drives the switch on demand:

```python
import textli

textli.set_theme("dark")     # or "light"
textli.toggle_theme()        # returns the new theme's name
textli.is_dark()             # -> bool
```

**Open editors restyle themselves.** Every `ZenMarkdownEditor` and
`InlineVimEditor` listens to `textli.theme_changed`, so the call above is
all a host needs — no cascade to wire up, no `apply_theme()` to remember.
Connect to the same signal to re-paint your own chrome alongside them:

```python
textli.theme_changed.connect(my_window.restyle)
```

If the host is *already* dark when it creates an editor, say so at
construction so the editor never paints a light frame first:

```python
ZenMarkdownEditor(parent=host, text=text, theme_name="dark")
```

`apply_theme()` is available on both widgets for the rare case where a host
changes colours without going through `set_theme` — it re-runs the
stylesheets, the syntax highlighting, and the read view's render (math and
chart images bake their ink at render time).

Inside textli, `⌘⇧D` toggles the palette and persists the choice; the
standalone app restores it at launch. That persistence belongs to the
standalone app only, so it can never override a host's choice.
