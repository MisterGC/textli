"""Source-code references in prose — ``textli/editor.py:2455`` — pure logic,
no Qt.

Agent-written documents (groundwork docs, reviews, retros) cite code as
repo-root-relative paths in inline code, optionally anchored to a line or a
range::

    `textli/editor.py`        `README.md`
    `textli/editor.py:2455`   `view.py:5089-5881`

This module answers the two questions the editor needs before it can follow
one: *is this chip a reference* (:func:`parse_ref`) and *which file on disk
does it mean* (:func:`resolve`). Both are deliberately conservative — a
false positive turns an innocent `identifier` chip into a dead "not found"
whisper, which is worse than not following at all.

The grammar therefore accepts a chip only when it carries a **file
extension** (``comments.py``) or an **explicit line anchor**
(``Makefile:12``). That keeps prose chips like ``-r/--read``, ``.md`` or
``setMarkdown`` out, at the price of a bare, extensionless ``Makefile``
chip not being followable (write ``Makefile:1``, or link it — a Markdown
link to a text file is routed on content, not on this grammar).

:func:`resolve` walks the document's folder and then its ancestors, nearest
match first, bounded by the enclosing git root (else ``$HOME``, else the
filesystem root) — so a doc in ``mgc/groundwork/`` finds ``textli/editor.py``
two hops up without the doc having to spell out ``../../``. A *bare* name
that the walk misses (``comments.py``, the way prose actually names a
module) falls back to one pruned sweep of the enclosing repository,
accepted only when exactly one file bears that name.

The walk is *lexical* (never realpath), so it cannot cycle through
symlinks, and it is hard-bounded by the path's own depth; the sweep prunes
vendored/cache trees, never follows symlinks, and gives up on a directory
budget. Every filesystem probe fails closed: an unreadable ancestor answers
"not here" instead of raising, so a permission-restricted chain ends in
None, never an exception.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

# Read at most this much of a file to decide text-vs-binary.
_SNIFF_BYTES = 4096

# Folders a bare-name search never descends into: version control, vendored
# code, caches, build output. They hold copies, not the file you meant.
_SCAN_SKIP = frozenset("""
    node_modules __pycache__ venv site-packages build dist target
    .git .venv .tox .mypy_cache .pytest_cache .idea .vscode .eggs
""".split())

# Directory budget for that search — a monorepo hits this and gives up
# (answering None) rather than making a keypress wait on the filesystem.
_SCAN_DIR_BUDGET = 4000

# ``:12``, ``:12-40`` — the dashes agents actually type (hyphen, en, em).
_RE_ANCHOR = re.compile(r":(\d+)(?:[-–—](\d+))?$")

# What a path may be made of. No ':' (the anchor is split off first), no
# whitespace, no shell/markup punctuation — those aren't paths in prose.
_RE_PATH = re.compile(r"^[A-Za-z0-9._+@~/-]+$")

# A plausible file extension: short, alphanumeric, and carrying at least one
# letter ('py', 'md', 'h', '7z') — so a version number like '3.14' is not a
# filename with a '.14' extension.
_RE_EXT = re.compile(r"^(?=[A-Za-z0-9]{1,8}$)[0-9]*[A-Za-z][A-Za-z0-9]*$")

# Extensions we take as text without opening the file.
_TEXT_SUFFIXES = frozenset("""
    py pyi qml js jsx ts tsx mjs cjs c h cc cpp cxx hpp hh cs java kt kts
    swift go rs rb php pl pm lua r jl scala clj sh bash zsh fish ps1 bat
    sql toml yaml yml json json5 ini cfg conf properties env txt text rst
    adoc org tex bib css scss sass less html htm xml svg xsl vue svelte
    gradle cmake make mk dockerfile gitignore gitattributes editorconfig
    lock csv tsv diff patch log md markdown
""".split())

# Extensions we refuse without opening the file — a decode sniff on a PNG
# would waste a read to reach the same answer.
_BINARY_SUFFIXES = frozenset("""
    png jpg jpeg gif bmp ico webp tiff pdf zip gz bz2 xz tar 7z rar
    exe dll so dylib bin o a lib class jar war pyc pyo pyd wasm
    mp3 mp4 wav ogg flac avi mov mkv webm ttf otf woff woff2 eot
    sqlite db dat pickle pkl npy npz
""".split())


# Text whose *point* is the rendered result, not the source. A link to
# 'page.html' or 'chart.svg' means "show me that" — the OS does it better than
# a code page would — so links to these stay with the system handler. A
# reference (`page.html:12`) still opens the source: naming a file in prose,
# and especially naming a line in it, is a statement about its text.
_VIEW_SUFFIXES = frozenset("html htm xhtml svg".split())


def prefers_external(path: str) -> bool:
    """True when a *link* to ``path`` is better handed to the OS than shown as
    source, even though the file is text (see :data:`_VIEW_SUFFIXES`)."""
    return os.path.basename(path).rpartition(".")[2].lower() in _VIEW_SUFFIXES


@dataclass(frozen=True)
class SourceRef:
    """A parsed reference: which file, and where in it to land."""

    path: str                 # the path exactly as written in the chip
    line: int | None = None   # 1-based anchor line, None = no anchor
    end_line: int | None = None   # last line of a ``:12-40`` range

    @property
    def lines(self) -> tuple[int, int] | None:
        """The anchored range as ``(first, last)``, 1-based and inclusive —
        None when the reference names no line. A reversed range (``:40-12``)
        is read in the order meant, not honored literally."""
        if self.line is None:
            return None
        last = self.end_line if self.end_line is not None else self.line
        return (min(self.line, last), max(self.line, last))


def parse_ref(text: str) -> SourceRef | None:
    """Read ``text`` (the content of one inline-code chip) as a source
    reference, or None when it isn't one.

    Pure string work — never touches the filesystem, so it is cheap enough
    to run over every chip on a page while rendering."""
    text = text.strip()
    if not text or any(ch.isspace() for ch in text):
        return None

    line = end = None
    path = text
    m = _RE_ANCHOR.search(text)
    if m:
        path = text[:m.start()]
        line = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else None

    if not path or not _RE_PATH.match(path) or path.endswith("/"):
        return None
    name = path.rsplit("/", 1)[-1]
    if name in ("", ".", ".."):
        return None
    # An extension needs a stem before it: '.md' in prose names a file *type*,
    # not a file. (Costs us dotfile refs like '.gitignore' — worth it.)
    stem, dot, ext = name.rpartition(".")
    has_ext = bool(dot and stem and _RE_EXT.match(ext))
    if not has_ext and line is None:
        return None
    return SourceRef(path=path, line=line, end_line=end)


def _exists(path: str) -> bool:
    """Fail-closed existence probe — an unreadable or malformed path is
    simply 'not here'. ``os.path`` swallows OSError already; ValueError
    covers embedded nulls."""
    try:
        return os.path.exists(path)
    except (OSError, ValueError):        # pragma: no cover - defensive
        return False


def _is_file(path: str) -> bool:
    """Fail-closed regular-file probe (see :func:`_exists`)."""
    try:
        return os.path.isfile(path)
    except (OSError, ValueError):        # pragma: no cover - defensive
        return False


def _ancestors(start: str):
    """``start`` and each of its parents, nearest first — purely lexical, so
    it terminates on the path's own depth and can't chase a symlink loop."""
    cur = os.path.abspath(start)
    while True:
        yield cur
        parent = os.path.dirname(cur)
        if parent == cur:            # the root is its own parent — done
            return
        cur = parent


def is_repo_root(path: str) -> bool:
    """True when ``path`` holds a ``.git`` — a directory in a normal clone, a
    file in a worktree, so existence (not type) is the test."""
    return _exists(os.path.join(path, ".git"))


def _scan_root(doc_dir: str) -> str | None:
    """The repository a bare-name search may look inside — the nearest
    ancestor holding a ``.git``, or None.

    ``$HOME`` is never a scan root even when it is itself a repo (a dotfiles
    clone is common), because scanning a whole home directory on a keypress
    is exactly the latency this feature must not introduce."""
    home = os.path.normpath(os.path.expanduser("~"))
    for anc in _ancestors(doc_dir):
        if anc == home:
            return None
        if is_repo_root(anc):
            return anc
    return None


def _find_unique(root: str, name: str) -> str | None:
    """The one file called ``name`` under ``root``, or None when there is
    none, more than one (ambiguous — guessing would be worse than a whisper),
    or the tree is too big to sweep within the budget.

    ``os.walk`` reports unreadable directories to a silent handler and does
    not follow symlinks, so this fails closed and cannot cycle."""
    match = None
    budget = _SCAN_DIR_BUDGET
    for dirpath, dirnames, filenames in os.walk(root):
        budget -= 1
        if budget <= 0:
            return None
        dirnames[:] = [d for d in dirnames
                       if d not in _SCAN_SKIP and not d.startswith(".")]
        if name in filenames:
            if match is not None:
                return None
            match = os.path.join(dirpath, name)
    return match


def resolve(path: str, doc_dir: str) -> str | None:
    """The absolute file ``path`` names when read from a document in
    ``doc_dir``, or None if no such file is reachable.

    Absolute and ``~`` paths are taken at face value. A relative path is
    tried against ``doc_dir`` first (so sibling references keep working),
    then against each ancestor — nearest wins — stopping *after* the
    enclosing git root, else after ``$HOME``, else at the filesystem root.

    A **bare filename** that no ancestor holds gets one last chance: a
    pruned sweep of the enclosing repository, accepted only if exactly one
    file bears that name. Prose names modules bare — CLAUDE.md's own
    architecture section says ``comments.py``, not ``textli/comments.py`` —
    and those are the references most worth following."""
    if not path:
        return None
    expanded = os.path.expanduser(path)
    if os.path.isabs(expanded):
        full = os.path.normpath(expanded)
        return full if _is_file(full) else None

    home = os.path.normpath(os.path.expanduser("~"))
    for anc in _ancestors(doc_dir):
        candidate = os.path.normpath(os.path.join(anc, expanded))
        if _is_file(candidate):
            return candidate
        if is_repo_root(anc) or anc == home:
            break                    # the bound is checked, not skipped

    if os.sep in expanded or (os.altsep and os.altsep in expanded):
        return None                  # a spelled-out path meant that path
    root = _scan_root(doc_dir)
    return _find_unique(root, expanded) if root else None


def display_path(path: str, doc_dir: str) -> str:
    """How to name ``path`` on screen: relative to the enclosing repository
    when it lives in one (``textli/editor.py``), else the bare file name — an
    absolute path would crowd the whisper off the card."""
    root = _scan_root(doc_dir) or _scan_root(os.path.dirname(path))
    if root:
        try:
            rel = os.path.relpath(path, root)
        except ValueError:                  # different drives (Windows)
            return os.path.basename(path)
        if not rel.startswith(".."):
            return rel
    return os.path.basename(path)


def is_texty(path: str) -> bool:
    """True when ``path`` should be read as source rather than handed to the
    OS: extension first, a content sniff for the rest (so an extensionless
    ``Makefile`` still opens and a mislabeled binary still doesn't). A path
    that isn't a readable regular file is never texty."""
    if not _is_file(path):
        return False
    suffix = os.path.basename(path).rpartition(".")[2].lower()
    if suffix in _BINARY_SUFFIXES:
        return False
    if suffix in _TEXT_SUFFIXES:
        return True
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(_SNIFF_BYTES)
    except OSError:
        return False
    if b"\x00" in chunk:                  # NUL — the classic binary tell
        return False
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError as exc:
        # A multi-byte char sliced by the read boundary is not evidence.
        return exc.start >= len(chunk) - 3
    return True


def fence(code: str, language: str = "") -> str:
    """``code`` as one fenced Markdown block, tagged ``language``.

    The fence is made longer than any backtick run inside ``code``, so a file
    that itself contains fences (this project's Markdown, say) can't close
    the block early."""
    longest = max((len(m.group(0)) for m in re.finditer(r"`+", code)),
                  default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{language}\n{code}\n{ticks}\n"
