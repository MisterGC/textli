# Writing

The write view is the Markdown source, syntax-highlighted, in a single
centered column. The editor opens here, in vim **NORMAL** mode.

!!! note "Key notation"
    `⌘` in this documentation is the editor's primary modifier — the key Qt
    reports as *Control* (`Cmd` on macOS, `Ctrl` on Linux/Windows).

## Vim editing

The essentials work the way your fingers expect:

- **Motions** — `h j k l`, `w / b / e`, `0 / $`, `gg / G`.
- **Entering INSERT** — `i a` (before/after the caret), `I A` (line
  start/end), `o O` (new line below/above). `Esc` returns to NORMAL.
- **Edits** — `x` (char), `dd` (line), `dw` (to next word).
- **VISUAL** — `v` starts a selection that the motions extend.

In NORMAL mode `Esc` saves and closes the editor; `⇧Esc` cancels and
discards pending changes.

## Focus

- `⌘.` toggles **section focus**: everything but the paragraph you're
  editing dims, so the sentence at hand is all that speaks.
- `⌘↵` toggles **full-window width** when you want the column to use the
  whole window.

## Layout & type

Both preferences persist across sessions:

- `⌘+` / `⌘-` / `⌘0` — font size bigger / smaller / reset.
- `⌘⇧→` / `⌘⇧←` / `⌘⇧↓` — content column wider / narrower / reset.

## Getting around

- `⌘J` opens the **word-jump overlay**: every visible word gets a two-key
  label; type the label to jump the caret there (Easymotion style).
- `/` (NORMAL mode) opens **search**: a live, ranked list of the lines your
  query matches — exact matches first, fuzzy ones by strength (weak
  scattered matches don't clutter the list at all). Move the selection to
  preview a hit, ++enter++ to jump, ++esc++ to stay where you were.
  Afterwards `n` / `N` step through the hits *in document order* (wrapping),
  with all hits highlighted. The same search works in the
  [reading view](reading.md).
- `⌘R` flips to the [reading view](reading.md) for proof-reading and review.
- `⌘P` prints.

## Files & saving

Opened on a file (the standalone `textli` CLI always is), the editor
**autosaves** while you type — there is no save command to remember. Lean on
git for durable checkpoints.
