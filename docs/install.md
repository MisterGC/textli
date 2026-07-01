# Install

textli is a Python package; the editor itself is built on Qt (PySide6),
which is installed automatically.

=== "uv"

    ```sh
    uv tool install textli
    ```

=== "pipx"

    ```sh
    pipx install textli
    ```

=== "pip"

    ```sh
    pip install textli
    ```

Python 3.12 or newer is required.

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
