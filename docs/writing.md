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
- **Undo / redo** — `u` undoes the last change, `⌃r` redoes it.
- **VISUAL** — `v` starts a selection that the motions extend; `d` / `y` / `c`
  then delete, yank or change it.
- **Yank & paste** — `yy` / `yw` yank a line / word, `p` / `P` paste after /
  before. Deletes (`x`, `dd`, `dw`) fill the same register, so a `dd` then `p`
  moves a line.
- **Counts** — a leading number repeats the next motion or edit: `3j`, `5w`,
  `2dd`, `4x`.

In NORMAL mode `Esc` saves and closes the editor; `⇧Esc` cancels and
discards pending changes.

## Focus

- `⌘.` toggles **section focus**: everything but the paragraph you're
  editing dims, so the sentence at hand is all that speaks.
- `⌘T` toggles **typewriter scrolling**: the caret line is held at a fixed
  height and the page moves under it, like the carriage of the machine it's
  named after — your eyes never chase the text down the screen. The
  preference persists.
- `⌘↵` toggles **full-window width** when you want the column to use the
  whole window.

## Layout & type

Both preferences persist across sessions:

- `⌘+` / `⌘-` / `⌘0` — font size bigger / smaller / reset.
- `⌘⇧→` / `⌘⇧←` / `⌘⇧↓` — content column wider / narrower / reset.

## Getting around

- `⌘J` opens the **word-jump overlay**: every visible word gets a two-key
  label; type the label to jump the caret there (Easymotion style).
- `gh` opens the **headings overview** — an outline of the document to jump
  through: `j`/`k` preview each heading live, ++enter++ keeps the spot,
  ++esc++ returns where you were. The same outline the
  [reading view](reading.md) offers, now over the source.
- `/` (NORMAL mode) opens **search**: a live, ranked list of the lines your
  query matches — exact phrases first, then lines where each query word
  fuzzy-matches *inside a single word* (`vrfy` finds *verify*; fuzzy never
  assembles a match from stray characters across the line). Move the
  selection to preview a hit, ++enter++ to jump, ++esc++ to stay where you
  were. Afterwards `n` / `N` step through the hits *in document order*
  (wrapping), with every match highlighted. The same search works in the
  [reading view](reading.md).
- ++enter++ (NORMAL mode) **follows the link under the caret** — anywhere
  inside `[text](url)`, an `<autolink>` or a bare URL. Web and mail targets
  open in your default browser; a `#heading-slug` target jumps to that
  heading, the same slugs the CLI's `file.md#heading` accepts.
- `⌘R` flips to the [reading view](reading.md) for proof-reading and review.
- `⌘P` prints.

## The whisper status

A single faint line in the card's bottom corner keeps you oriented without
asking for attention: the vim mode, the word count, and — once you've
changed something — the session delta (`NORMAL · 1,234 words · +56`).
It hides whenever a card (search, open, overview) is up, and in the
[reading view](reading.md) it turns into reading progress instead.

## Files & saving

Opened on a file (the standalone `textli` CLI always is), the editor
**autosaves** while you type — there is no save command to remember. Lean on
git for durable checkpoints.

It also **watches the file** and reflects changes made outside textli — an
agent rewriting the doc from the comments you just left, a `git` checkout,
another app — **in place**, keeping your view, caret and scroll, with a faint
*reloaded* whisper. So the read → comment → "update the doc from my comments"
→ read loop needs no restart to see the result. If you happen to have unsaved
edits of your own when the file changes underneath you, textli holds off
rather than clobbering either side: it whispers a warning and keeps what
you're typing (which wins on the next autosave). Reconciling a genuine
two-sided conflict is coming.

The editor also **holds your place**: closing a file remembers the view you
were in and where — reopening it (CLI or `go`) resumes exactly there, in the
[reading view](reading.md) too. Explicit targets win: `-r` forces the
reading view, a `#heading-slug` location overrides the remembered spot.
