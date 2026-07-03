# Keybindings

The complete reference — the same content the editor shows on `F1`.
`⌘` is the editor's primary modifier (`Cmd` on macOS, `Ctrl` elsewhere).

## Views & session

| Key | Action |
| --- | --- |
| `⌘R` | Toggle the source editor ↔ rendered reading view |
| `Esc` | Save & close (`⇧Esc` cancels / discards pending changes) |
| `⌘↵` | Toggle full-window width |
| `⌘.` | Section focus — dim all but the current paragraph |
| `⌘T` | Typewriter scrolling — hold the caret line steady while writing (persists) |
| `⌘+` / `⌘-` / `⌘0` | Font size bigger / smaller / reset (persists) |
| `⌘⇧→` / `⌘⇧←` / `⌘⇧↓` | Content column wider / narrower / reset (persists) |
| `⌘J` | Word-jump overlay (Easymotion-style two-key jump) |
| `⌘P` | Print |
| `F1` | Help |

## Writing (vim — source editor)

| Key | Action |
| --- | --- |
| `h j k l` | Move left / down / up / right |
| `w / b / e` | Next word / previous word / word end |
| `0 / $` · `gg / G` | Line start / end · document start / end |
| `i a` · `I A` · `o O` | Enter INSERT: before/after · line start/end · new line below/above |
| `Esc` | Back to NORMAL mode |
| `x` · `dd` · `dw` | Delete char · line · to next word |
| `go` | Open another file — history is fuzzy-matched, paths complete per segment |

## Search (`/`) — both views

| Key | Action |
| --- | --- |
| `/` | Search the document — matching lines ranked best-first (exact above fuzzy) |
| (type) | Live hit list; the view scrolls to preview the selected hit |
| `⌃n / ⌃p` · `↓ / ↑` | Move the selection |
| `Enter` · `Esc` | Jump to the hit · cancel back to where you were |
| `n / N` | Next / previous hit (wraps; the query survives `⌘R`) |

## Open-file dialog (`go`)

| Key | Action |
| --- | --- |
| (type) | Fuzzy-match your history (files & their folders); a path (with `/` or `~`) also completes the filesystem, segment by segment |
| `⌃n / ⌃p` · `↓ / ↑` | Move the selection |
| `Tab` | Complete — extend to the common prefix, else adopt the selected row |
| `Enter` | Open the selected file (a directory descends into it); with no match, open the typed path as a new file |
| `Esc` | Cancel, back to the editor |

See [Opening files](opening.md) for how the matching works.

## Reading view — navigate

| Key | Action |
| --- | --- |
| `h j k l` · `w b e` · `0 $` | Move a caret through the rendered text |
| `gg / G` | Document start / end |
| `⌃d / ⌃u` · `⌃f / ⌃b / Space` | Half-page · full-page scroll |
| `gh` | Headings overview — `j`/`k` preview live, `Enter` keeps, `Esc` restores your spot |
| `go` | Open another file (stays in the reading view) |

## Reading view — comments

| Key | Action |
| --- | --- |
| `v` | Visual mode — extend a selection with the motions above |
| `c` | Comment the selection (or reveal/edit the comment under the caret) |
| `]c / [c` | Step to the next / previous comment |
| `Enter` · `⇧D` | Reveal-edit · delete the active comment |

## Reading view — suggestions (track changes)

| Key | Action |
| --- | --- |
| `s` | Suggest a change — replace the selection (empty = delete), or insert at the caret |
| `]s / [s` | Step to the next / previous suggestion |
| `a / x` | Accept / reject the suggestion under the caret and advance to the next |
| `⇧A / ⇧X` | Accept / reject all suggestions at once |
| `gc` | Changes overview — every change & comment, same live preview as `gh` |
| `p` | Clean preview — the prose with every suggestion accepted (source untouched) |
