# Inline Annotation as a Collaboration Substrate: Notes on the Design and Performance of textli

*An example paper following the textli skill's paper playbook — its
object of research is textli itself, so every source reference below is
followable: put the caret on one and press Enter; `gb` comes back.*

## Abstract

Document review between humans and AI agents usually routes annotations
through a side channel — proprietary track-changes formats, review-tool
databases, or pull-request comments detached from the text. textli
instead stores comments and suggested edits inline in the Markdown file
as CriticMarkup [1], so a review round-trip needs nothing but the file
itself. This note describes the two design problems that model creates —
parsing annotations robustly inside prose, and re-locating them after
Markdown rendering destroys all source offsets — and the sentinel-based
rendering technique that solves the second. It also reports two
rendering-cost results from the implementation: batching style merges
into one edit block cuts the per-merge cost from about 1 ms to about
1.5 µs, taking a 4,500-line document from 15 s to interactive open, and
replacing a per-span line scan with binary search removes a
$\Theta(s \cdot n)$ hotspot that accounted for 1.7 s of a 2 s open. The
result is a review surface where annotations travel with the document,
diff in git, and render at reading speed.

## 1. Introduction

Prose review has a portability problem. Word processors keep track
changes in an opaque format; review platforms keep comments in their own
database, anchored to line numbers that drift; and plain Markdown — the
format humans and AI agents actually exchange — has no standard review
layer at all. The consequence is that the *document* travels but the
*conversation about it* does not.

textli's premise is that the conversation should live in the file. It
adopts CriticMarkup [1] — `{>>comments<<}` and
`{++insert++}`/`{--delete--}`/`{~~replace~~}` suggestions as plain text
spans — and builds a typeset reading view in which those marks render as
highlights and navigable track changes rather than as syntax.

This note contributes:

1. a single-file annotation model in which comments and suggestions are
   tempered CriticMarkup that survives any transport that preserves the
   Markdown (§3.1);
2. a sentinel-based technique for carrying span identity through a
   Markdown renderer that discards source offsets (§3.2);
3. two measured rendering-cost results — edit-block batching and
   span-to-line bisection — that make the approach practical on large
   documents (§4).

## 2. Related work

**Track changes in word processors** offer the same accept/reject
semantics but couple them to an application-private file format; the
annotations are unreadable without the tool. textli differs by making
the raw file legible and diffable — the marks are ASCII in the source.

**Platform review (pull requests, Google Docs)** anchors comments
outside the document, in a service. The anchoring breaks when text moves
between systems; textli's marks cannot detach because they *are* text.

**CriticMarkup tooling** [1] historically focused on syntax highlighting
and preprocessing to HTML. textli treats the format as a live review
surface: marks are first-class objects with navigation, resolution
keys, and animation, not just colored spans.

## 3. Design

### 3.1 A tempered inline format

Annotations inside prose must not swallow each other: a comment body
that happens to contain `{==` must not extend a neighboring span. The
parser therefore uses *tempered* regular expressions — each inner
position is checked not to open or close another marker — so one
malformed or adjacent mark cannot consume the rest of the document
(`textli/comments.py:36`; the suggestion patterns are tempered the same
way, `textli/comments.py:470`). The parsing layer is pure Python with no
Qt dependency, which keeps the format's semantics unit-testable outside
the editor.

### 3.2 Sentinel-based rendering

Rendering is the hard problem: Qt's Markdown import consumes the source
and produces a rich-text document with no mapping back to source
offsets, yet a commented span must be highlighted in the rendered
output. textli wraps each annotated span in private-use code points
(U+E000 / U+E001) that pass through the renderer as invisible text
(`textli/comments.py:412`). After rendering, the reading view locates
the sentinel pairs in the rich-text document, applies character formats
tagged with the mark's index, and deletes the sentinels
(`textli/editor.py:223`). Because the formats carry the index as a
custom property, a span fragmented by intervening layout still maps back
to its source annotation.

### 3.3 Resolving a suggestion

Accepting or rejecting a suggestion mutates the source file, which
triggers a re-render and reflow. Running the visual transition *after*
the mutation would animate against already-moved text, so the animator
fades the leaving span first and only then applies the undoable source
edit (`textli/suggest.py:40`).

## 4. Evaluation

Both results below are measured on the motivating workload — a
4,500-line annotated Markdown document — on a development machine; see
§5 for scope.

| Optimization | Before | After |
| --- | --- | --- |
| Edit-block batching of style merges | ~1 ms per merge; 15 s open | ~1.5 µs per merge |
| Span→line lookup by binary search | 21M steps; 1.7 s of a 2 s open | negligible |

**Batching.** Outside an edit block, every character- or block-format
merge settles the document layout again, so a styling pass over a
document whose merge count grows with its length is quadratic in
practice. Grouping each render pass into one edit block defers layout to
the end of the pass, measured at roughly 1 ms per merge unbatched
against 1.5 µs batched (`textli/editor.py:172`).

**Bisection.** Syntax-highlighting a fenced code block maps highlight
spans back to document lines. Scanning every line for every span costs

$$T(s, n) = \Theta(s \cdot n)$$

for $s$ spans over $n$ lines — 21 million steps on a whole-file fence,
1.7 s of a 2 s open. Binary-searching the span's opening line over the
sorted line starts and walking only the lines it covers reduces this to
$\Theta(s \log n + k)$, where $k$ is the number of span–line overlaps —
in practice $k \approx s$, since a highlight span almost never crosses a
line (`textli/editor.py:2569`).

## 5. Discussion & limitations

The single-file premise buys portability at visible cost: the marks are
syntax in the write view, and a heavily-reviewed paragraph reads noisily
in raw source — the reading view, not the source, is the intended review
surface. The model is also single-document and asynchronous: two writers
editing simultaneously are arbitrated by the file watcher (the open
editor holds its unsaved edits and warns rather than merging), not by
real-time co-editing. The math layer renders the TeX subset without
custom macros, which keeps sources portable to pandoc but rules out
notation-heavy fields' house styles. Finally, the numbers in §4 are
measurements from this one codebase and machine, recorded at the
optimization sites rather than in a controlled harness — they size the
effects, they are not a benchmark study.

## 6. Conclusion

Storing review inline as tempered CriticMarkup makes the document itself
the collaboration substrate: annotations survive any channel that
carries the file, including git. The rendering problem that model
creates is solvable with sentinel pass-through, and two targeted
optimizations make it fast enough that a large annotated document opens
at reading speed.

## References

1. CriticMarkup — <http://criticmarkup.com/>
2. Pandoc User's Guide, "Math" — <https://pandoc.org/MANUAL.html#math>
3. Qt Rich Text Processing (QTextDocument) — <https://doc.qt.io/qt-6/richtext.html>
4. textli repository — <https://github.com/MisterGC/textli>
