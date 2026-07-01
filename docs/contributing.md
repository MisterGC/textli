# Contributing

Issues and pull requests are welcome at
[github.com/MisterGC/textli](https://github.com/MisterGC/textli).

## Development setup

```sh
git clone https://github.com/MisterGC/textli
cd textli
uv venv && uv pip install -e '.[dev]'
```

## Running the tests

The suite runs headless against Qt's offscreen platform:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
```

CI runs the same suite on Linux (under xvfb) and macOS, on Python 3.12
and 3.13.

## Docs

The documentation is built with MkDocs Material and deployed to GitHub
Pages on every push to `main`:

```sh
uv pip install -e '.[docs]'
.venv/bin/mkdocs serve
```

## Layout

| Module | Role |
| --- | --- |
| `textli/editor.py` | `ZenMarkdownEditor` — the full-window editor and reading view |
| `textli/vim.py` | The vim key handler shared by all editing surfaces |
| `textli/highlight.py` | Markdown syntax highlighting + paragraph focus |
| `textli/jump.py` | The word-jump (Easymotion-style) overlay |
| `textli/suggest.py` | Accept/reject animation for suggestions |
| `textli/comments.py` | CriticMarkup parsing, authoring, and application (pure Python) |
| `textli/inline_editor.py` | `InlineVimEditor` — the embeddable single-field editor |
| `textli/app.py` | The standalone `textli` CLI host |
| `textli/constants.py` | Palette, layout, and modifier constants |
| `textli/fonts.py` | Bundled JetBrains Mono registration |
