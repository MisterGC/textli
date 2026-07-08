# textli

A lightweight text editor with focused writing and reading in mind.

textli is a full-window, distraction-free Markdown editor: one warm
paper-toned column of text, vim keybindings, and nothing else on screen.
`⌘R` flips the source into a rendered **reading view** made for
proof-reading and review — navigate with vim motions, leave inline
**comments**, and propose **suggestions** (track changes) that the author
accepts or rejects with a keystroke. All annotations are stored inline as
[CriticMarkup](http://criticmarkup.com/), so they travel with the file and
diff cleanly in git — no sidecar files.

textli started life as the editor inside [grafli](https://github.com/MisterGC/grafli),
the keyboard-driven diagram tool, and is now its own package — usable
standalone or embeddable in any PySide6 application.

## Install

```sh
uv tool install textli-editor   # or: pipx / pip install textli-editor
```

The package publishes as `textli-editor` (plain `textli` is too close to an
existing PyPI name), but everywhere else it's just textli: the command is
`textli`, the import is `import textli`.

## Use

```sh
textli notes.md                     # open (created on first save)
textli notes.md#design-decisions    # jump straight to a heading
textli -r review.md                 # start in the reading view
```

The editor opens ready to type (vim NORMAL mode) and autosaves while you
work, and every file **resumes where you left it** — view mode, caret and
scroll included. A faint **whisper status** in the card's corner keeps you
oriented —
mode, word count, and session delta while writing; progress, minutes left,
and open review items while reading. Press `F1` inside the editor for the
complete key reference, or see the
[documentation](https://mistergc.github.io/textli/).

### The short version

| Key | Action |
| --- | --- |
| `⌘R` | Toggle write ↔ reading view |
| `Esc` | Save & close (`⇧Esc` cancels) |
| `⌘↵` | Full-window width |
| `⌘.` | Section focus (dim all but the current paragraph / section) |
| `⌘T` | Typewriter scrolling (the caret line stays put; persists) |
| `c` / `s` | Comment / suggest a change on the selection (reading view) |
| `a` / `x` | Accept / reject the suggestion under the caret |
| `go` | Open another file — fuzzy history + per-segment path completion |
| `↵` | Follow the link under the caret (both views; `#heading` jumps in-document) |
| `/` | Fuzzy in-document search (`n`/`N` next/previous hit) |
| `F1` | Full help |

## Embed

```python
from textli import ZenMarkdownEditor, InlineVimEditor
```

`ZenMarkdownEditor` is the full-window editor (parent it into any widget);
`InlineVimEditor` is a small vim-capable `QPlainTextEdit` for editing a single
piece of text in place. See the
[embedding guide](https://mistergc.github.io/textli/embedding/).

## Develop

```sh
uv venv && uv pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
```

## License

MIT — see [LICENSE](LICENSE). Bundled fonts are licensed under the
[SIL Open Font License](textli/fonts/OFL.txt).
