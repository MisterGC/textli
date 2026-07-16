# Keybindings

The complete reference — the same content the editor shows on `F1`.
`⌘` is the editor's primary modifier (`Cmd` on macOS, `Ctrl` elsewhere).

## Views & session

| Key | Action |
| --- | --- |
| `⌘R` | Toggle the source editor ↔ rendered reading view |
| `Esc` | Save & close (`⇧Esc` cancels / discards pending changes) |
| `⌘↵` | Toggle full-window width |
| `⌘.` | Section focus — dim all but the current paragraph (writing) / section (reading) |
| `⌘T` | Typewriter scrolling — hold the caret line steady while writing (persists) |
| `⌘⇧P` | Paper surface — grain & light under the text; off = the flat page (persists) |
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
| `x` · `dd` · `dw` | Delete char · line · to next word (into the register) |
| `u` · `⌃r` | Undo · redo the last change |
| `v` | VISUAL — extend a selection with the motions, then `d` / `y` / `c` |
| `yy` · `yw` · `p` / `P` | Yank line / word · paste after / before |
| `2j` · `3dd` | A leading count repeats the next motion or edit |
| `↵` | Follow the link under the caret — web/mail in the browser, `#heading` jumps there (NORMAL mode) |
| `go` | Open another file — history is fuzzy-matched, paths complete per segment |
| `gh` | Headings overview — an outline of the source (`j`/`k` preview, `Enter` keeps, `Esc` restores) |

## Search (`/`) — both views

| Key | Action |
| --- | --- |
| `/` | Search the document — matching lines ranked best-first (exact above fuzzy) |
| (type) | Live hit list; the view scrolls to preview the selected hit |
| `⌃n / ⌃p` · `↓ / ↑` | Move the selection |
| `Enter` · `Esc` | Jump to the hit · cancel back to where you were |
| `n / N` | Next / previous hit (wraps; the query survives `⌘R`) |
| `⇥` (write view) | Reveal replace — `↵` replaces this match & advances, `⌃↵` replaces all (literal matches) |

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
| `f` | Focus reading mode — caret-lock at centre + a spotlight on the reading line, fading text by distance (persists) |
| `gh` | Headings overview — `j`/`k` preview live, `Enter` keeps, `Esc` restores your spot |
| `gl` | Links overview — same jump-list; `Enter` follows the picked link |
| `↵` | Follow the link under the caret — a `.md` opens in place, web/mail in the browser, `#heading` jumps there, anything else via the system handler |
| `↵` | Follow the **source reference** under the caret — `editor.py`, `textli/editor.py:2455`, `view.py:80-95` — opening the file read-only at that line (see [Source references](#source-references)) |
| `gb` / `⌫` | Back to the document (or source file) the last link or reference was followed from |
| `go` | Open another file (stays in the reading view) |

## Source references

Notes about code — a design doc, a review, anything an agent wrote — cite
files the way everyone writes them: `` `textli/editor.py:2455` ``,
`` `view.py:80-95` ``, or just `` `editor.py` ``. In the reading view those
are followable: `↵` opens the file **in place**, read-only, at that line, and
`gb` (or `⌫`) brings you back exactly where you were — so you can check the
code a decision rests on without leaving the page you're reading.

| | |
| --- | --- |
| What counts | An inline-code span carrying a file extension (`comments.py`) or a line anchor (`Makefile:12`). Prose chips (`--read`, `.md`, `QWidget`) are left alone. |
| Where it looks | Beside the document first, then up through the parent folders — so a doc in `mgc/groundwork/` finds `textli/editor.py` without spelling out `../../`. A bare name (`editor.py`) is then looked up in the repository; if two files share the name, textli says *not found* rather than guess. |
| How far it looks | Never past the enclosing repository (or your home folder). Nothing resolves outside it. |
| What you get | The file in monospace on the code band, syntax-highlighted, sized and widened for code, with the referenced lines lifted onto the bright page. `⌘+`/`⌘-` zoom, `/` searches, vim motions move — the page just isn't editable. |
| What it won't do | Comment, suggest, or edit — `c`/`s`/`⌘R` whisper instead. textli annotates Markdown; a peeked file isn't yours to mark up. |

A link works too: `[the module](../textli/editor.py)` opens as source, while a
link to something meant to be *seen* (`page.html`, an image, a PDF) still goes
to the system handler.

## Reading view — comments

| Key | Action |
| --- | --- |
| `v` | Visual mode — extend a selection with the motions above |
| `c` | Comment the selection or the formula under the caret (or reveal/edit the comment there) |
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
