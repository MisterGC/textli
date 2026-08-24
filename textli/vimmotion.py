"""Vim motions and text objects over a plain string — pure text logic, no Qt.

The vim handler in :mod:`textli.vim` is a Qt coordinator: it reads the caret
position out of a ``QPlainTextEdit``, asks this module *where a motion lands* or
*what span a text object covers*, and turns the answer back into a cursor move
or an edit. Everything that can be decided from the text alone lives here, so
the word-boundary rules — the part that actually has to feel like vim — stay
cheap to unit-test without a widget.

Positions are absolute offsets into the document string, which is exactly what
``QTextDocument`` positions are once line breaks are plain ``\\n``.

Two conventions the caller depends on:

* A **motion** returns a single position. Whether the character it lands on is
  part of an operated-on span is the caller's business (``e`` is inclusive,
  ``w`` is not) — this module reports the landing place, not the span.
* A **text object** returns a half-open ``(start, end)`` span, the same
  convention as Python slicing.

Word motions use vim's three character classes — blank, word (alphanumeric and
``_``), and punctuation — so ``w`` stops between ``foo`` and ``(`` the way it
does in vim, rather than treating the whole of ``foo(bar)`` as one word. The
``big`` flag collapses word and punctuation into one class, which is the
difference between ``w`` and ``W``.
"""

from __future__ import annotations

BLANK, WORD, PUNCT = 0, 1, 2

_BLANKS = " \t"


def char_class(ch: str, big: bool = False) -> int:
    """Vim's character class for ``ch``. ``big`` folds word and punctuation
    together — everything that isn't blank is one class, which is what makes
    ``W``/``B``/``E`` whitespace-delimited."""
    if ch in _BLANKS or ch == "\n":
        return BLANK
    if big or ch.isalnum() or ch == "_":
        return WORD
    return PUNCT


# ── Lines ──

def line_bounds(text: str, pos: int) -> tuple[int, int]:
    """The ``(start, end)`` of the line holding ``pos``, end exclusive of the
    newline. A position at the very end of the text belongs to the last line."""
    pos = max(0, min(pos, len(text)))
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return start, len(text) if end < 0 else end


def line_start(text: str, pos: int) -> int:
    """``0`` — the first column of this line."""
    return line_bounds(text, pos)[0]


def line_end(text: str, pos: int) -> int:
    """``$`` — the last column of this line (the newline itself is not part of
    the line, so an empty line reports its own start)."""
    return line_bounds(text, pos)[1]


def first_non_blank(text: str, pos: int) -> int:
    """``^`` — the first non-blank column. A line with nothing but blanks on it
    reports its end, which is where vim's ``^`` leaves the caret there."""
    start, end = line_bounds(text, pos)
    while start < end and text[start] in _BLANKS:
        start += 1
    return start


def line_number(text: str, pos: int) -> int:
    """The 1-based line number holding ``pos``."""
    return text.count("\n", 0, max(0, min(pos, len(text)))) + 1


def goto_line(text: str, n: int) -> int:
    """The first non-blank of 1-based line ``n``, clamped to the last line —
    where ``gg`` / ``G`` / ``<count>G`` land."""
    lines = text.count("\n") + 1
    n = max(1, min(n, lines))
    pos = 0
    for _ in range(n - 1):
        pos = text.find("\n", pos) + 1
    return first_non_blank(text, pos)


def _is_empty_line(text: str, pos: int) -> bool:
    """True when ``pos`` sits at the start of a line with nothing on it. Vim's
    word motions stop on empty lines, which is why they need naming."""
    if pos >= len(text) or text[pos] != "\n":
        return False
    return pos == 0 or text[pos - 1] == "\n"


# ── Word motions ──

def word_forward(text: str, pos: int, count: int = 1, big: bool = False) -> int:
    """``w`` / ``W`` — the start of the next word."""
    n = len(text)
    for _ in range(count):
        if pos >= n:
            break
        if _is_empty_line(text, pos):
            pos += 1
        else:
            cls = char_class(text[pos], big)
            if cls != BLANK:
                while pos < n and char_class(text[pos], big) == cls:
                    pos += 1
        while (pos < n and char_class(text[pos], big) == BLANK
               and not _is_empty_line(text, pos)):
            pos += 1
    return min(pos, n)


def word_end(text: str, pos: int, count: int = 1, big: bool = False) -> int:
    """``e`` / ``E`` — the last character of the current or next word. Inclusive:
    the caller operating on it must cover the landing character too."""
    n = len(text)
    for _ in range(count):
        if pos >= n - 1:
            return max(0, n - 1)
        pos += 1
        while pos < n and char_class(text[pos], big) == BLANK:
            pos += 1
        if pos >= n:
            return max(0, n - 1)
        cls = char_class(text[pos], big)
        while pos + 1 < n and char_class(text[pos + 1], big) == cls:
            pos += 1
    return min(pos, max(0, n - 1))


def word_backward(text: str, pos: int, count: int = 1, big: bool = False) -> int:
    """``b`` / ``B`` — the start of the current or previous word."""
    for _ in range(count):
        pos -= 1
        if pos <= 0:
            return 0
        if _is_empty_line(text, pos):
            continue
        while (pos > 0 and char_class(text[pos], big) == BLANK
               and not _is_empty_line(text, pos)):
            pos -= 1
        if _is_empty_line(text, pos):
            continue
        cls = char_class(text[pos], big)
        while pos > 0 and char_class(text[pos - 1], big) == cls:
            pos -= 1
    return max(0, pos)


# ── Paragraph motions ──

def paragraph_forward(text: str, pos: int, count: int = 1) -> int:
    """``}`` — the next empty line, or the end of the text."""
    n = len(text)
    for _ in range(count):
        _s, e = line_bounds(text, pos)
        p = e
        landed = False
        while p < n:
            p += 1                      # step onto the next line
            s2, e2 = line_bounds(text, p)
            if s2 == e2:                # an empty line is the boundary
                pos, landed = s2, True
                break
            p = e2
        if not landed:
            pos = n
    return pos


def paragraph_backward(text: str, pos: int, count: int = 1) -> int:
    """``{`` — the previous empty line, or the start of the text."""
    for _ in range(count):
        s, _e = line_bounds(text, pos)
        p = s
        landed = False
        while p > 0:
            p -= 1                      # step onto the previous line
            s2, e2 = line_bounds(text, p)
            if s2 == e2:
                pos, landed = s2, True
                break
            p = s2
        if not landed:
            pos = 0
    return pos


# ── Character search ──

def find_char(text: str, pos: int, ch: str, count: int = 1,
              *, forward: bool = True, till: bool = False) -> int | None:
    """``f`` / ``F`` / ``t`` / ``T`` — search for ``ch`` within this line only.

    Returns ``None`` when the character isn't there, which vim treats as a
    failed motion: nothing moves and a pending operator is abandoned.
    """
    if not ch:
        return None
    start, end = line_bounds(text, pos)
    cur = pos
    for _ in range(count):
        if forward:
            found = text.find(ch, cur + 1, end)
        else:
            found = text.rfind(ch, start, cur)
        if found < 0:
            return None
        cur = found
    if till:
        cur += -1 if forward else 1
    return cur


def matching_bracket(text: str, pos: int) -> int | None:
    """``%`` — from the first bracket at or after the caret (on this line), the
    position of its match, nesting-aware. ``None`` when there's nothing to match."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    reverse = {v: k for k, v in pairs.items()}
    _s, end = line_bounds(text, pos)
    at = None
    for i in range(max(0, pos), end):
        if text[i] in pairs or text[i] in reverse:
            at = i
            break
    if at is None:
        return None
    ch = text[at]
    if ch in pairs:
        depth, i, close = 0, at, pairs[ch]
        while i < len(text):
            if text[i] == ch:
                depth += 1
            elif text[i] == close:
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return None
    depth, i, open_ = 0, at, reverse[ch]
    while i >= 0:
        if text[i] == ch:
            depth += 1
        elif text[i] == open_:
            depth -= 1
            if depth == 0:
                return i
        i -= 1
    return None


# ── Text objects ──
#
# Each returns a half-open (start, end) span, or None when there is nothing
# under the caret to take — a failed object abandons the pending operator.

def word_object(text: str, pos: int, count: int = 1,
                *, inner: bool, big: bool = False) -> tuple[int, int] | None:
    """``iw`` / ``aw`` — the word under the caret. ``aw`` also takes the trailing
    whitespace, or the leading whitespace when there is none after it."""
    n = len(text)
    if n == 0:
        return None
    pos = max(0, min(pos, n - 1))
    if text[pos] == "\n":
        return None

    def run_bounds(at: int) -> tuple[int, int]:
        cls = char_class(text[at], big)
        s = at
        while s > 0 and text[s - 1] != "\n" and char_class(text[s - 1], big) == cls:
            s -= 1
        e = at
        while e + 1 < n and text[e + 1] != "\n" and char_class(text[e + 1], big) == cls:
            e += 1
        return s, e + 1

    start, end = run_bounds(pos)
    # A count takes further runs: for `iw` whitespace counts as its own run
    # (vim's `2iw` is word + following space), for `aw` a whole word each.
    for _ in range(count - 1):
        if end >= n or text[end] == "\n":
            break
        if inner:
            _s2, end = run_bounds(end)
        else:
            nxt = end
            while nxt < n and text[nxt] != "\n" and char_class(text[nxt], big) == BLANK:
                nxt += 1
            if nxt >= n or text[nxt] == "\n":
                break
            _s2, end = run_bounds(nxt)
    if inner:
        return start, end
    trailing = end
    while trailing < n and text[trailing] in _BLANKS:
        trailing += 1
    if trailing > end:
        return start, trailing
    while start > 0 and text[start - 1] in _BLANKS:
        start -= 1
    return start, end


def quote_object(text: str, pos: int, quote: str,
                 *, inner: bool) -> tuple[int, int] | None:
    """``i"`` / ``a"`` (also ``'`` and `````) — the quoted run on this line.

    Vim looks forward from the caret when it isn't already inside one, so an
    operator typed anywhere before the opening quote still finds the string.
    Backslash-escaped quotes don't count as delimiters.
    """
    start, end = line_bounds(text, pos)
    marks: list[int] = []
    i = start
    while i < end:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            marks.append(i)
        i += 1
    for a, b in zip(marks[::2], marks[1::2]):
        if pos <= b:
            return (a + 1, b) if inner else (a, b + 1)
    return None


def bracket_object(text: str, pos: int, open_: str, close: str,
                   *, inner: bool) -> tuple[int, int] | None:
    """``i(`` / ``a(``, ``i[``, ``i{``, ``i<`` — the bracketed span around the
    caret, nesting-aware and free to span lines. A caret resting *on* either
    bracket counts as inside, the way vim treats it."""
    n = len(text)
    if pos >= n:
        pos = max(0, n - 1)
    # Opening bracket: scan back, tracking closes we pass so a sibling pair
    # doesn't get mistaken for our own opener.
    depth, i, a = 0, pos, None
    while i >= 0:
        if text[i] == close and i != pos:
            depth += 1
        elif text[i] == open_:
            if depth == 0:
                a = i
                break
            depth -= 1
        i -= 1
    if a is None:
        return None
    depth, i, b = 0, a, None
    while i < n:
        if text[i] == open_:
            depth += 1
        elif text[i] == close:
            depth -= 1
            if depth == 0:
                b = i
                break
        i += 1
    if b is None:
        return None
    return (a + 1, b) if inner else (a, b + 1)


def paragraph_object(text: str, pos: int,
                     *, inner: bool) -> tuple[int, int] | None:
    """``ip`` / ``ap`` — the run of non-blank lines around the caret. ``ap`` also
    takes the blank lines after it (or before, when it ends the document)."""
    n = len(text)
    s, e = line_bounds(text, pos)
    blank_start = s == e
    # Walk out while the lines match the caret line's blank-ness, the way vim
    # treats a caret sitting in the gap between paragraphs.
    start = s
    while start > 0:
        ps, pe = line_bounds(text, start - 1)
        if (ps == pe) != blank_start:
            break
        start = ps
    end = e
    while end < n:
        ns, ne = line_bounds(text, end + 1)
        if (ns == ne) != blank_start:
            break
        end = ne
    if inner:
        return start, end
    tail = end
    while tail < n:
        ns, ne = line_bounds(text, tail + 1)
        if ns != ne:
            break
        tail = ne
    if tail > end:
        return start, tail
    while start > 0:
        ps, pe = line_bounds(text, start - 1)
        if ps != pe:
            break
        start = ps
    return start, end
