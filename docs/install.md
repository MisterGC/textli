# Install

textli is a Python package; the editor itself is built on Qt (PySide6),
which is installed automatically.

=== "uv"

    ```sh
    uv tool install textli-editor
    ```

=== "pipx"

    ```sh
    pipx install textli-editor
    ```

=== "pip"

    ```sh
    pip install textli-editor
    ```

Python 3.12 or newer is required.

!!! note "textli-editor?"
    The distribution publishes as `textli-editor` — plain `textli` is too
    close to an existing PyPI name. Everywhere else it's just **textli**:
    the command is `textli`, the import is `import textli`.

## The CLI

```sh
textli notes.md                     # open a file reading (created on first save)
textli notes.md#design-decisions    # open and jump to a heading
textli -w notes.md                  # start in the editable write view
textli notes.md --pdf               # write notes.pdf and exit, no window
textli notes.md --pdf out/paper.pdf # ... or to a path you name
```

- The `#fragment` is a Markdown heading slug, exactly as in a Markdown link.
- File-backed editing **autosaves** while you work; `Esc` closes the session,
  `⇧Esc` discards pending changes.
- `--pdf` exports the typeset reading page — charts, diagrams and math
  included — without opening a window, so a draft becomes a shareable paper
  from a script or a Makefile. Paper is never themed: the page comes out on
  the light palette whatever theme you read in.
- Font size and content-column width adjustments persist across sessions.
