"""Tokenizing fenced code for the read view — pure text logic, no Qt.

Pygments does the lexing; this module reduces its rich token taxonomy to the
four classes the zen scheme colors (``keyword``, ``string``, ``comment``,
``number``) and reports them as offset spans into the *unmodified* code
string, so the editor can map them straight onto rendered document
positions. Anything Pygments can't help with — unknown language, no
language, Pygments missing entirely — degrades to "no spans": the block
still gets its band, the code simply stays ink.
"""

from __future__ import annotations

try:
    from pygments.lexers import get_lexer_by_name
    from pygments.token import Comment, Keyword, Number, Operator, String
    from pygments.util import ClassNotFound
    _HAVE_PYGMENTS = True
except ImportError:                                   # pragma: no cover
    _HAVE_PYGMENTS = False


def _classify(ttype) -> str | None:
    """Map a Pygments token type to a zen class (or None → stays ink)."""
    if ttype in Keyword.Constant:
        return "number"        # True/None/nil — constants wear amber
    if ttype in Keyword or ttype in Operator.Word:
        return "keyword"       # incl. `and`/`or`/`not`
    if ttype in String:
        return "string"
    if ttype in Comment:
        return "comment"
    if ttype in Number:
        return "number"
    return None


def highlight_spans(code: str, language: str) -> list[tuple[int, int, str]]:
    """Spans ``(start, end, class)`` to color in ``code`` per ``language``.

    Offsets index ``code`` exactly as passed (the lexer is configured not to
    strip or append anything). Unknown/empty language or no Pygments → []."""
    if not (_HAVE_PYGMENTS and language):
        return []
    try:
        lexer = get_lexer_by_name(language, stripnl=False, ensurenl=False)
    except ClassNotFound:
        return []
    spans: list[tuple[int, int, str]] = []
    pos = 0
    for ttype, value in lexer.get_tokens(code):
        cls = _classify(ttype)
        if cls is not None and value:
            spans.append((pos, pos + len(value), cls))
        pos += len(value)
    return spans
