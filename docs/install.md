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
textli notes.md                     # open a file (created on first save)
textli notes.md#design-decisions    # open and jump to a heading
textli -r review.md                 # start in the rendered reading view
```

- The `#fragment` is a Markdown heading slug, exactly as in a Markdown link.
- File-backed editing **autosaves** while you work; `Esc` closes the session,
  `⇧Esc` discards pending changes.
- Font size and content-column width adjustments persist across sessions.
