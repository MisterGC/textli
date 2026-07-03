# Opening files

You never have to leave the editor to work on another note: press `go` — in
the write view (vim NORMAL mode) or in the reading view — and the **open-file
dialog** appears: an input line over a live suggestion list, entirely
keyboard-driven. The current file is autosaved, so switching is instant and
dialog-free; opened from the reading view, the new file opens reading too.

## Two kinds of matching

The dialog deliberately matches two sources differently, so results stay
predictable:

**Your history — fuzzy, over the full path.** textli remembers the files you
open (and the folders that contained them). These are matched fuzzily against
everything you type: start typing `special` and
`/my/cool/special_path/notes.md` surfaces immediately, even though you typed
none of its leading segments. Matches at word starts and in the file name
rank higher, and recently opened files win ties.

**The filesystem — completed per segment.** A query that looks like a path
(contains a `/`, or starts with `~`) also completes against the real
filesystem, but only shell-style, one segment at a time: `/Ho` suggests
`/Home`, never some deep `/some/other/dir/Home` you've never visited. Only
folders and `.md` files are offered; hidden entries appear when the segment
you're typing starts with a `.`.

History rows are marked with a filled dot (●), filesystem completions with a
hollow one (○). Folders end in `/` — selecting one descends into it and
lists its subfolders and Markdown files, exactly like the `mydocs/` folder of
a note you once opened.

## Keys

| Key | Action |
| --- | --- |
| (type) | Filter — history fuzzy + per-segment path completion |
| `⌃n / ⌃p` · `↓ / ↑` | Move the selection |
| `Tab` | Complete — extend to the common prefix, else adopt the selected row |
| `Enter` | Open the selected file; on a folder, descend into it |
| `Esc` | Cancel, back to the editor |

## New files

Type a path that doesn't exist yet (in a folder that does) and press
`Enter` with no match selected: the editor opens an empty buffer on it.
Like the CLI, the file is created on your first save — merely looking never
touches the disk.

## History size

The history keeps the **200** most recently opened files (least recently
used entries fall off). Together with the folders derived from them this
stays a personal, high-signal set — large enough to cover months of writing,
small enough that fuzzy results never feel noisy. It persists across
sessions alongside the editor's other preferences.
