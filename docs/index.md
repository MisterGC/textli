# textli

**A lightweight text editor with focused writing and reading in mind.**

textli puts one warm, paper-toned column of text on screen and nothing else.
It opens ready to type — vim NORMAL mode, autosave on — and one keystroke
(`⌘R`) flips the Markdown source into a rendered **reading view** built for
proof-reading and review.

## What it does

- **Focused writing** — a distraction-free, full-window surface with vim
  keybindings (NORMAL / INSERT / VISUAL), section focus that dims everything
  but the paragraph you're in, and an Easymotion-style word-jump overlay.
- **A real reading view** — the rendered document, navigated with the same
  vim motions, with a headings outline (`gh`) one key away.
- **Typeset mathematics** — pandoc-style `$…$` and `$$…$$` render as real
  formulas in the reading view, and review like any other span; the source
  stays plain pandoc, so a draft converts to LaTeX or PDF untouched.
- **Notes that reach their code** — a reference like `textli/editor.py:2455`
  is followable: ++enter++ opens the file read-only at that line, `gb` comes
  back. A design doc keeps its evidence one keystroke away instead of
  pasted in and going stale.
- **Inline review** — leave comments on any span, or propose *suggestions*
  (track changes) that the author steps through and accepts or rejects with
  single keys. A changes overview (`gc`) lists every mark; a clean preview
  (`p`) shows the prose as if everything were accepted.
- **No sidecar files** — comments and suggestions are stored inline as
  [CriticMarkup](http://criticmarkup.com/), so they travel with the Markdown
  and diff cleanly in git. Made for humans and AI agents reviewing each
  other's prose.
- **Embeddable** — the editor is a plain PySide6 widget. Host it in your own
  app; [grafli](https://github.com/MisterGC/grafli), the keyboard-driven
  diagram tool it grew up in, does exactly that.

## Quick start

```sh
uv tool install textli-editor
textli notes.md
```

Type. `Esc` saves and closes. `F1` shows the complete key reference at any
time — the same help whether textli runs standalone or embedded.

## Where to go next

- [Install](install.md) — install options and the CLI.
- [Writing](writing.md) — the write view: vim, focus, layout.
- [Reading & review](reading.md) — the reading view, comments, and
  suggestions.
- [Keybindings](keybindings.md) — the full reference.
- [Embedding](embedding.md) — using the editor widgets in your own PySide6
  app.
