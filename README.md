# textli

A lightweight text editor with focused writing and reading in mind.

textli is a full-window, distraction-free Markdown editor: one warm
paper-toned column of text, vim keybindings, and nothing else on screen.
`⌘R` flips the source into a rendered **reading view** made for
proof-reading and review — navigate with vim motions, leave inline
**comments**, and propose **suggestions** (track changes) that the author
accepts or rejects with a keystroke. Notes *about code* stay connected to it:
a reference like `textli/editor.py:2455` is followable — `↵` opens the file
read-only at that line, `gb` comes back — so a design doc reads with its
evidence one keystroke away. All annotations are stored inline as
[CriticMarkup](http://criticmarkup.com/), so they travel with the file and
diff cleanly in git — no sidecar files. Pandoc-style **TeX math** — `$…$`
inline, `$$…$$` display — renders as typeset formulas in the reading view,
so scientific notes read like the paper they'll become (and convert to one
via pandoc, untouched). A `<!-- chart: bar x=… -->` marker over a pipe table
turns it into a typeset **chart** on render, while the source stays a plain
table everywhere else. And an image reference to a `.grafli` file —
`![](architecture.grafli)` — renders inline as the **diagram** itself when the
[grafli](https://github.com/MisterGC/grafli) CLI is installed, degrading
quietly to nothing when it isn't.

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
scroll included. It also **watches the open file**, so edits made outside
textli (an agent applying your comments, a `git` checkout) reload in place
without a restart. A faint **whisper status** in the card's corner keeps you
oriented —
mode, word count, and session delta while writing; the section you're in,
progress, minutes left, and open review items while reading. Press `F1` inside the editor for the
complete key reference, or see the
[documentation](https://mistergc.github.io/textli/).

### The short version

| Key | Action |
| --- | --- |
| `⌘R` | Toggle write ↔ reading view |
| `Esc` | Save & close (`⇧Esc` cancels) |
| `⌘↵` | Full-window width |
| `⌘.` | Section focus (dim all but the current paragraph / section) |
| `f` | Focus reading mode — caret-locked centre line + gradient spotlight (reading view) |
| `⌘T` | Typewriter scrolling (the caret line stays put; persists) |
| `⌘⇧P` | Paper surface — grain & light on the page; off = flat (persists) |
| `c` / `s` | Comment / suggest a change on the selection — text or a formula (reading view) |
| `a` / `x` | Accept / reject the suggestion under the caret |
| `go` | Open another file — fuzzy history + per-segment path completion |
| `↵` | Follow the link under the caret — `.md` opens in place, web in the browser, `#heading` jumps (reading view) |
| `↵` | Follow the source reference under the caret — `` `editor.py:42` `` opens the file read-only at that line (reading view) |
| `gb` / `⌫` | Back to the document the last link was followed from (reading view) |
| `gl` | Links overview — jump-list of every link (reading view) |
| `/` | Fuzzy in-document search (`n`/`N` next/previous hit; `⇥` to replace) |
| `F1` | Full help |

## Embed

```python
from textli import ZenMarkdownEditor, InlineVimEditor
```

`ZenMarkdownEditor` is the full-window editor (parent it into any widget);
`InlineVimEditor` is a small vim-capable `QPlainTextEdit` for editing a single
piece of text in place. See the
[embedding guide](https://mistergc.github.io/textli/embedding/).

## AI agents

textli ships an installable **agent skill** that teaches AI tools to author
Markdown for the reading view and to review through the inline annotation
layer — comments from the human, track-change suggestions from the agent —
including genre playbooks (decision doc, learning doc, scientific paper;
`examples/paper.md` is a worked example studying textli itself):

```sh
textli skill install     # ~/.claude/skills, ~/.agents/skills, ~/.config/opencode/skills
textli skill check       # per-tool status: ok / stale / modified / missing
textli skill             # print the whole skill to stdout instead
```

See the [AI agents guide](https://mistergc.github.io/textli/ai/).

## Develop

```sh
uv venv && uv pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
```

## License

MIT — see [LICENSE](LICENSE). Bundled fonts — JetBrains Mono, Caveat and
Literata — are licensed under the SIL Open Font License
([JetBrains Mono](textli/fonts/OFL.txt), [Caveat](textli/fonts/Caveat-OFL.txt),
[Literata](textli/fonts/Literata-OFL.txt)).
