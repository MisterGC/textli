"""Colour palette — light and dark, swappable at runtime.

Every colour the editor paints comes from here. Modules read roles as module
attributes::

    from textli import theme
    painter.fillRect(rect, theme.ZEN_MD_BG)

Access is deliberately ``theme.X`` rather than ``from theme import X``: the
module globals are rebound when the theme switches, so a plain attribute read
always yields the active value. A ``from``-import would freeze the palette at
whatever was active when the module was first imported — which is exactly the
bug this module exists to prevent, and what ``test_no_module_level_bindings``
guards against.

The two palettes are **counterparts, not inversions**. Light is warm paper
(``#EEE5D0``) with near-black ink; dark is the same warm hue family rotated to
a low-key ground (``#1E1C19``, shared with grafli so an embedded editor sits
on its host's board) carrying the light theme's paper colour as its ink.

Dark values are *derived* from the light theme's measured relationships, never
carried across it:

* Roles that are readable **by luminance** in light reproduce their contrast
  ratio against the ground they are actually drawn on — syntax tokens against
  the code band, not against the page.
* Roles that are readable **by hue** in light (the amber number token measures
  only 1.74:1 on the light band) keep their hue identity and clear a
  readability floor instead; reproducing their ratio on a dark ground yields
  muddy, invisible olive.
* Anything drawn *on a fill* takes its ink from that fill via :func:`ink_on`,
  so a hardcoded light ink can never survive the ground changing under it.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, fields, replace

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor

from textli.constants import ZEN_MD_CALLOUT_TINT_ALPHA


def _flatten(fg: QColor, bg: QColor) -> QColor:
    """Composite translucent ``fg`` over opaque ``bg`` → an opaque colour."""
    a = fg.alphaF()
    return QColor(
        round(bg.red() * (1 - a) + fg.red() * a),
        round(bg.green() * (1 - a) + fg.green() * a),
        round(bg.blue() * (1 - a) + fg.blue() * a),
    )


@dataclass(frozen=True)
class Palette:
    """One complete set of colour roles."""

    name: str
    is_dark: bool

    # ── Page & surfaces ──────────────────────────────────────────
    ZEN_MD_BG: QColor                # the page itself
    ZEN_MD_CODE_BG: QColor           # inline-code chip
    ZEN_MD_CODE_BLOCK_BG: QColor     # fenced-code band
    ZEN_MD_TABLE_HEADER_BG: QColor
    ZEN_CARD_BG: QColor              # overlay card paper
    ZEN_CARD_BORDER: QColor
    ZEN_FIELD_BG: QColor             # line-edit inside a card
    ZEN_BACKDROP: QColor             # standalone host backdrop

    # ── Ink ──────────────────────────────────────────────────────
    ZEN_TEXT_COLOR: QColor
    ZEN_TITLE_COLOR: QColor
    ZEN_HINT_COLOR: QColor
    ZEN_MD_LINK_COLOR: QColor
    ZEN_MD_SYNTAX_COLOR: QColor
    ZEN_MD_TABLE_BORDER: QColor
    ZEN_INK_ON_LIGHT_FILL: QColor    # text over a bright fill
    ZEN_INK_ON_DARK_FILL: QColor     # text over a dark fill

    # ── Code tokens (drawn on the band) ──────────────────────────
    ZEN_CODE_KEYWORD: QColor
    ZEN_CODE_STRING: QColor
    ZEN_CODE_COMMENT: QColor
    ZEN_CODE_NUMBER: QColor

    # ── Annotation layer ─────────────────────────────────────────
    ZEN_MD_COMMENT_INK: QColor
    ZEN_MD_COMMENT_HL: QColor        # translucent wash behind a commented span
    ZEN_MD_COMMENT_SELECTION: QColor  # selection inside the comment note field
    ZEN_MD_SUGGEST_ADD: QColor
    ZEN_MD_OUTLINE_MARK: QColor      # the faint `#` level marks in an overview

    # ── Navigation & selection ───────────────────────────────────
    ZEN_MD_CARET: QColor
    ZEN_SELECTION_BG: QColor
    ZEN_SEARCH_HIT: QColor
    ZEN_SEARCH_CURRENT: QColor
    ZEN_JUMP_BADGE_BG: QColor
    ZEN_JUMP_DIM: QColor

    # ── Washes ───────────────────────────────────────────────────
    ZEN_MD_DIM_COLOR: QColor         # card chrome dim
    ZEN_MD_CANVAS_DIM_COLOR: QColor  # host canvas dim

    # ── Derived (filled in by _derive) ───────────────────────────
    ZEN_MD_COMMENT_NOTE_BG: QColor = field(default_factory=QColor)
    ZEN_MD_SRC_ANCHOR_BG: QColor = field(default_factory=QColor)


def _derive(p: Palette) -> Palette:
    """Fill the roles that are defined *by* other roles, so they can never
    drift out of step with the palette they belong to."""
    return replace(
        p,
        # The note editor wears the exact tint a commented span gets in the
        # text — the wash flattened over the page — so the note you write and
        # the mark it leaves read as one thing.
        ZEN_MD_COMMENT_NOTE_BG=_flatten(p.ZEN_MD_COMMENT_HL, p.ZEN_MD_BG),
        # A source-page anchor lifts back out of the band onto the bright
        # page: the mark is *removing* shade, so it is the page colour.
        ZEN_MD_SRC_ANCHOR_BG=QColor(p.ZEN_MD_BG),
    )


LIGHT = _derive(Palette(
    name="light",
    is_dark=False,

    ZEN_MD_BG=QColor("#EEE5D0"),
    ZEN_MD_CODE_BG=QColor("#EDE9E3"),
    ZEN_MD_CODE_BLOCK_BG=QColor("#E5DAC0"),
    ZEN_MD_TABLE_HEADER_BG=QColor("#E5DAC0"),
    ZEN_CARD_BG=QColor("#FBF7EC"),
    ZEN_CARD_BORDER=QColor("#C9A227"),
    ZEN_FIELD_BG=QColor("#FFFFFF"),
    ZEN_BACKDROP=QColor("#23272A"),

    ZEN_TEXT_COLOR=QColor("#403A30"),
    ZEN_TITLE_COLOR=QColor("#004578"),
    ZEN_HINT_COLOR=QColor("#8A8580"),
    ZEN_MD_LINK_COLOR=QColor("#004578"),
    ZEN_MD_SYNTAX_COLOR=QColor("#B8B3AB"),
    ZEN_MD_TABLE_BORDER=QColor("#C7B99B"),
    ZEN_INK_ON_LIGHT_FILL=QColor("#2D2D2D"),
    ZEN_INK_ON_DARK_FILL=QColor("#F2F0EB"),

    ZEN_CODE_KEYWORD=QColor("#004578"),
    ZEN_CODE_STRING=QColor("#A83E2E"),
    ZEN_CODE_COMMENT=QColor("#8A8580"),
    ZEN_CODE_NUMBER=QColor("#C9A227"),

    ZEN_MD_COMMENT_INK=QColor("#6E2A1C"),
    ZEN_MD_COMMENT_HL=QColor(199, 92, 78, 72),
    ZEN_MD_COMMENT_SELECTION=QColor("#E7C6A0"),
    ZEN_MD_SUGGEST_ADD=QColor("#A83E2E"),
    ZEN_MD_OUTLINE_MARK=QColor("#A2937A"),

    ZEN_MD_CARET=QColor(0, 69, 120, 72),
    ZEN_SELECTION_BG=QColor("#B8D4E8"),
    ZEN_SEARCH_HIT=QColor(201, 162, 39, 60),
    ZEN_SEARCH_CURRENT=QColor(201, 162, 39, 135),
    ZEN_JUMP_BADGE_BG=QColor("#004578"),
    ZEN_JUMP_DIM=QColor(245, 242, 237, 200),

    ZEN_MD_DIM_COLOR=QColor(0, 0, 0, 115),
    ZEN_MD_CANVAS_DIM_COLOR=QColor(0, 0, 0, 165),
))


# Dark. Each value below reproduces the light theme's relationship against the
# ground the role actually sits on; the measured ratios are in the comments so
# a later edit is checked against the rule, not against taste.
DARK = _derive(Palette(
    name="dark",
    is_dark=True,

    # The ground, and surfaces that step *off* it by the same amount the light
    # surfaces step off paper (band 1.11, chip 1.04, card 1.17) — the
    # direction flips because there is no room below a low-key ground.
    ZEN_MD_BG=QColor("#1E1C19"),
    ZEN_MD_CODE_BG=QColor("#21201B"),          # 1.04 vs page
    ZEN_MD_CODE_BLOCK_BG=QColor("#272421"),    # 1.10 vs page
    ZEN_MD_TABLE_HEADER_BG=QColor("#272421"),
    ZEN_CARD_BG=QColor("#2C2923"),             # 1.17 vs page
    ZEN_CARD_BORDER=QColor("#C9A227"),         # amber identity, kept by hue
    ZEN_FIELD_BG=QColor("#34302A"),            # a step above the card
    ZEN_BACKDROP=QColor("#141310"),            # below the page, as in light

    # Ink. The light theme's paper becomes the ink; the rest reproduce their
    # measured contrast against the page.
    ZEN_TEXT_COLOR=QColor("#EEE5D0"),
    ZEN_TITLE_COLOR=QColor("#77B8E2"),         # 7.88 (light 7.89)
    ZEN_HINT_COLOR=QColor("#696460"),          # 2.91 (light 2.92)
    ZEN_MD_LINK_COLOR=QColor("#77B8E2"),
    ZEN_MD_SYNTAX_COLOR=QColor("#45403A"),     # 1.66 (light 1.66)
    ZEN_MD_TABLE_BORDER=QColor("#453B27"),     # 1.54 (light 1.55)
    ZEN_INK_ON_LIGHT_FILL=QColor("#2D2D2D"),
    ZEN_INK_ON_DARK_FILL=QColor("#F2F0EB"),

    # Code tokens, measured on the band they are drawn on.
    ZEN_CODE_KEYWORD=QColor("#78B7E2"),        # 7.11 on band (light 7.12)
    ZEN_CODE_STRING=QColor("#DF634E"),         # 4.43 on band (light 4.46)
    ZEN_CODE_COMMENT=QColor("#6A635B"),        # 2.61 on band (light 2.63)
    # Amber is the exception: its light-theme readability is hue separation,
    # not luminance (1.74 on the light band). Matching that ratio here gives
    # an unreadable olive, so the hue is kept and the token clears the
    # readability floor instead.
    ZEN_CODE_NUMBER=QColor("#D8B64A"),

    ZEN_MD_COMMENT_INK=QColor("#ECA393"),      # 8.28 (light 8.33)
    # The wash keeps its *subtlety* rather than its exact composite: lifting a
    # dark ground costs the light ink contrast, so holding the alpha near the
    # light value leaves the wash soft and the text more readable, not less.
    ZEN_MD_COMMENT_HL=QColor(199, 92, 78, 90),
    ZEN_MD_COMMENT_SELECTION=QColor("#5A3B17"),  # 1.07 on the note (light 1.06)
    ZEN_MD_SUGGEST_ADD=QColor("#E0644E"),      # 4.94 (light 4.94)
    ZEN_MD_OUTLINE_MARK=QColor("#796B55"),     # 2.79 on the card (light 2.81)

    ZEN_MD_CARET=QColor(119, 184, 226, 80),
    ZEN_SELECTION_BG=QColor("#2E4457"),
    ZEN_SEARCH_HIT=QColor(201, 162, 39, 70),
    ZEN_SEARCH_CURRENT=QColor(201, 162, 39, 130),
    ZEN_JUMP_BADGE_BG=QColor("#77B8E2"),
    ZEN_JUMP_DIM=QColor(30, 28, 25, 200),

    ZEN_MD_DIM_COLOR=QColor(0, 0, 0, 115),
    ZEN_MD_CANVAS_DIM_COLOR=QColor(0, 0, 0, 165),
))


PALETTES = {"light": LIGHT, "dark": DARK}

_ROLE_NAMES = tuple(f.name for f in fields(Palette)
                    if f.name not in ("name", "is_dark"))


class _Notifier(QObject):
    changed = Signal()


_notifier = _Notifier()
#: Emitted after the active palette changes. Hosts embedding the widgets can
#: connect to this instead of cascading ``apply_theme()`` by hand.
changed = _notifier.changed

_active = LIGHT


def current() -> Palette:
    """The active palette."""
    return _active


def is_dark() -> bool:
    """True when the dark palette is active."""
    return _active.is_dark


def name() -> str:
    """The active palette's name — ``"light"`` or ``"dark"``."""
    return _active.name


def _install(palette: Palette) -> None:
    global _active
    _active = palette
    g = globals()
    for role in _ROLE_NAMES:
        g[role] = getattr(palette, role)
    g["IS_DARK"] = palette.is_dark


def set_theme(theme_name: str) -> bool:
    """Activate a palette by name. Returns True when the theme actually
    changed (so callers can skip a needless restyle)."""
    palette = PALETTES.get(theme_name)
    if palette is None or palette is _active:
        return False
    _install(palette)
    _notifier.changed.emit()
    return True


def toggle() -> str:
    """Switch to the other palette; returns the new theme's name."""
    set_theme("light" if _active.is_dark else "dark")
    return _active.name


@contextmanager
def as_palette(palette: Palette):
    """Run a block with ``palette`` installed, then restore.

    For rendering to a medium that isn't the screen — paper isn't themed, so
    printing and PDF export draw on the light palette whatever the reader has
    active. Deliberately silent: ``changed`` never fires, so open widgets
    don't restyle themselves around a print they aren't part of.
    """
    previous = _active
    if palette is previous:
        yield
        return
    _install(palette)
    try:
        yield
    finally:
        _install(previous)


#: Which existing role each callout kind (:mod:`textli.callouts`) borrows its
#: accent from. Callouts get no colours of their own — the box is a wash of a
#: role that is already in the palette — so they can never drift out of it on a
#: theme switch. Roles are named rather than bound here for the same reason
#: every other module reads ``theme.X`` late.
#:
#: The warm palette has no green and no purple, so GitHub's five hues map onto
#: the five identities it does have: the title/link blue for plain information,
#: the hint gray for a tip (the quietest voice, because a tip is optional
#: reading), the two annotation reds for what must not be missed, and the amber
#: that already means *attention* on the card border and the search hit.
CALLOUT_ACCENT_ROLES = {
    "NOTE": "ZEN_TITLE_COLOR",
    "TIP": "ZEN_HINT_COLOR",
    "IMPORTANT": "ZEN_MD_COMMENT_INK",
    "WARNING": "ZEN_CODE_NUMBER",
    "CAUTION": "ZEN_MD_SUGGEST_ADD",
}


def callout_accent(kind: str) -> QColor:
    """The accent a callout kind wears — its label ink and its left bar."""
    return QColor(getattr(_active, CALLOUT_ACCENT_ROLES[kind]))


def callout_fill(kind: str) -> QColor:
    """The box tint: the kind's accent laid over the page at whisper strength.

    Flattened to an opaque colour rather than left translucent, so the box
    prints as it reads — a block background is one of the few read-view cues
    that survives ``⌘P``, and a page rendered on the light palette must not
    depend on what the block happens to sit on.
    """
    wash = QColor(callout_accent(kind))
    wash.setAlpha(ZEN_MD_CALLOUT_TINT_ALPHA)
    return _flatten(wash, _active.ZEN_MD_BG)


def ink_on(fill: QColor) -> QColor:
    """Readable text colour for anything drawn on top of ``fill``.

    Pinning a light ink only looks right while the fill happens to be dark —
    which stops being true the moment the palette lifts that fill. Deriving
    the ink from the fill is the one rule that survives a theme switch, so
    every badge and chip goes through here rather than hardcoding.
    """
    luma = 0.299 * fill.red() + 0.587 * fill.green() + 0.114 * fill.blue()
    return QColor(ZEN_INK_ON_LIGHT_FILL if luma > 140
                  else ZEN_INK_ON_DARK_FILL)


_install(LIGHT)
