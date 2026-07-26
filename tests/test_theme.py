"""The two counterpart palettes, and the relationships that must survive a
switch.

These tests deliberately assert *rules*, not colours: a palette edit is
checked against the relationship that made the original value correct, so the
class of bug where a value is carried across the inversion (a light ink left
pinned over a fill the dark palette lifted) fails here rather than in the eye.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402

from textli import theme  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_light():
    yield
    theme.set_theme("light")


# ── contrast helpers (WCAG relative luminance) ───────────────────

def _channel(c: int) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(c: QColor) -> float:
    return (0.2126 * _channel(c.red())
            + 0.7152 * _channel(c.green())
            + 0.0722 * _channel(c.blue()))


def _contrast(a: QColor, b: QColor) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _flatten(fg: QColor, bg: QColor) -> QColor:
    a = fg.alphaF()
    return QColor(
        round(bg.red() * (1 - a) + fg.red() * a),
        round(bg.green() * (1 - a) + fg.green() * a),
        round(bg.blue() * (1 - a) + fg.blue() * a),
    )


# ── palette structure ────────────────────────────────────────────

def test_both_palettes_define_every_role():
    for role in theme._ROLE_NAMES:
        assert isinstance(getattr(theme.LIGHT, role), QColor)
        assert isinstance(getattr(theme.DARK, role), QColor)


def test_the_palettes_are_actually_different():
    differing = [r for r in theme._ROLE_NAMES
                 if getattr(theme.LIGHT, r) != getattr(theme.DARK, r)]
    # A handful of roles are shared on purpose (the ink_on endpoints, the dim
    # washes) — but the palette as a whole must be a counterpart, not a copy.
    assert len(differing) > len(theme._ROLE_NAMES) * 0.7


def test_dark_inverts_the_ground_ink_relationship():
    """Ink contrasts with the page in both themes, from opposite sides."""
    assert _luminance(theme.LIGHT.ZEN_TEXT_COLOR) < \
        _luminance(theme.LIGHT.ZEN_MD_BG)
    assert _luminance(theme.DARK.ZEN_TEXT_COLOR) > \
        _luminance(theme.DARK.ZEN_MD_BG)


def test_body_ink_is_readable_in_both_themes():
    for p in (theme.LIGHT, theme.DARK):
        assert _contrast(p.ZEN_TEXT_COLOR, p.ZEN_MD_BG) >= 7.0, p.name


# ── the relationships that must survive the inversion ────────────

@pytest.mark.parametrize("role", [
    "ZEN_TITLE_COLOR", "ZEN_HINT_COLOR", "ZEN_MD_SYNTAX_COLOR",
    "ZEN_MD_TABLE_BORDER", "ZEN_MD_SUGGEST_ADD", "ZEN_MD_COMMENT_INK",
])
def test_page_inks_keep_their_contrast_role(role):
    """A role's contrast against its own page encodes how loud it is meant to
    be. Dark reproduces the ratio rather than the value."""
    light = _contrast(getattr(theme.LIGHT, role), theme.LIGHT.ZEN_MD_BG)
    dark = _contrast(getattr(theme.DARK, role), theme.DARK.ZEN_MD_BG)
    assert dark == pytest.approx(light, rel=0.10), (
        f"{role}: light {light:.2f} vs dark {dark:.2f}")


@pytest.mark.parametrize("role", [
    "ZEN_CODE_KEYWORD", "ZEN_CODE_STRING", "ZEN_CODE_COMMENT",
])
def test_code_tokens_measured_against_the_band(role):
    """Syntax tokens are drawn on the code band, not on the page — measuring
    them against the page is what produced an unreadable dark amber."""
    light = _contrast(getattr(theme.LIGHT, role),
                      theme.LIGHT.ZEN_MD_CODE_BLOCK_BG)
    dark = _contrast(getattr(theme.DARK, role),
                     theme.DARK.ZEN_MD_CODE_BLOCK_BG)
    assert dark == pytest.approx(light, rel=0.10), (
        f"{role}: light {light:.2f} vs dark {dark:.2f}")


def test_every_code_token_is_readable_on_its_band():
    """The floor the amber token fails in light and must not fail in dark:
    a token whose light readability comes from hue rather than luminance is
    allowed to be *louder* in dark, never quieter."""
    for p in (theme.LIGHT, theme.DARK):
        for role in ("ZEN_CODE_KEYWORD", "ZEN_CODE_STRING",
                     "ZEN_CODE_COMMENT", "ZEN_CODE_NUMBER"):
            got = _contrast(getattr(p, role), p.ZEN_MD_CODE_BLOCK_BG)
            assert got >= 1.7, f"{p.name}/{role} = {got:.2f}"
    # The amber token specifically: dark must not inherit light's weak ratio.
    assert _contrast(theme.DARK.ZEN_CODE_NUMBER,
                     theme.DARK.ZEN_MD_CODE_BLOCK_BG) >= 4.5


def test_surfaces_step_off_the_page_by_the_same_amount():
    """The code band, chip and card read as containers because of how far they
    sit from the page — the step is preserved even though its direction flips
    (there is no room below a low-key ground)."""
    for role in ("ZEN_MD_CODE_BG", "ZEN_MD_CODE_BLOCK_BG", "ZEN_CARD_BG"):
        light = _contrast(getattr(theme.LIGHT, role), theme.LIGHT.ZEN_MD_BG)
        dark = _contrast(getattr(theme.DARK, role), theme.DARK.ZEN_MD_BG)
        assert dark == pytest.approx(light, rel=0.10), role


def test_text_stays_readable_through_every_wash():
    """A comment highlight and a search hit are washes you read *through*."""
    for p in (theme.LIGHT, theme.DARK):
        for role in ("ZEN_MD_COMMENT_HL", "ZEN_SEARCH_HIT",
                     "ZEN_SEARCH_CURRENT"):
            flat = _flatten(getattr(p, role), p.ZEN_MD_BG)
            got = _contrast(p.ZEN_TEXT_COLOR, flat)
            assert got >= 4.5, f"{p.name}/{role} = {got:.2f}"


def test_search_and_comment_washes_stay_distinguishable():
    """Hits read as navigation and comments as annotation — if the two washes
    converge, the reader can no longer tell them apart at a glance."""
    for p in (theme.LIGHT, theme.DARK):
        comment = _flatten(p.ZEN_MD_COMMENT_HL, p.ZEN_MD_BG)
        current = _flatten(p.ZEN_SEARCH_CURRENT, p.ZEN_MD_BG)
        hit = _flatten(p.ZEN_SEARCH_HIT, p.ZEN_MD_BG)
        # different hue families, and the current hit is the louder of the two
        assert abs(comment.hue() - current.hue()) > 10, p.name
        assert _contrast(current, p.ZEN_MD_BG) > _contrast(hit, p.ZEN_MD_BG), \
            p.name


def test_ink_on_flips_with_the_fill():
    """The one rule that survives a palette switch."""
    assert theme.ink_on(QColor("#1E1C19")) == theme.ZEN_INK_ON_DARK_FILL
    assert theme.ink_on(QColor("#EEE5D0")) == theme.ZEN_INK_ON_LIGHT_FILL


def test_ink_on_is_readable_for_every_fill_it_is_used_with():
    for name in ("light", "dark"):
        theme.set_theme(name)
        for fill in (theme.ZEN_JUMP_BADGE_BG, theme.ZEN_CARD_BORDER,
                     theme.ZEN_MD_BG, theme.ZEN_CODE_NUMBER):
            got = _contrast(theme.ink_on(fill), fill)
            assert got >= 3.0, f"{name}: {fill.name()} = {got:.2f}"


def test_derived_roles_follow_the_palette_they_belong_to():
    """The comment note wears the wash flattened over its own page — it must
    never keep the other palette's tint."""
    for p in (theme.LIGHT, theme.DARK):
        assert p.ZEN_MD_COMMENT_NOTE_BG == _flatten(p.ZEN_MD_COMMENT_HL,
                                                    p.ZEN_MD_BG)
        assert p.ZEN_MD_SRC_ANCHOR_BG == p.ZEN_MD_BG


# ── switching ────────────────────────────────────────────────────

def test_set_theme_rebinds_module_attributes():
    theme.set_theme("light")
    assert theme.ZEN_MD_BG == theme.LIGHT.ZEN_MD_BG
    theme.set_theme("dark")
    assert theme.ZEN_MD_BG == theme.DARK.ZEN_MD_BG
    assert theme.IS_DARK is True


def test_set_theme_rejects_unknown_and_is_a_noop_when_unchanged():
    theme.set_theme("light")
    assert theme.set_theme("chartreuse") is False
    assert theme.set_theme("light") is False
    assert theme.set_theme("dark") is True


def test_toggle_round_trips():
    theme.set_theme("light")
    assert theme.toggle() == "dark"
    assert theme.is_dark() is True
    assert theme.toggle() == "light"
    assert theme.is_dark() is False


def test_changed_fires_only_on_a_real_change():
    theme.set_theme("light")
    seen = []
    theme.changed.connect(lambda: seen.append(1))
    theme.set_theme("light")
    assert seen == []
    theme.set_theme("dark")
    assert len(seen) == 1


def test_no_module_level_bindings_freeze_the_palette():
    """The trap this module exists to close: a ``from theme import X`` in any
    editor module would capture the colour active at import time and never
    follow a switch again."""
    import pathlib
    import re
    src_dir = pathlib.Path(theme.__file__).parent
    offenders = []
    # Only *colour roles* are rebound by _install, so importing the functions
    # (set_theme, is_dark, …) or the signal by name is fine — the package root
    # re-exports exactly those as the public API.
    pattern = re.compile(
        r"^from (?:(?:textli\.)|\.)theme import ([^\n]+)", re.M)
    for path in src_dir.glob("*.py"):
        if path.name == "theme.py":
            continue
        for imported in pattern.findall(path.read_text(encoding="utf-8")):
            names = {n.strip().split(" as ")[0].strip("(), ")
                     for n in imported.split(",")}
            frozen = names & set(theme._ROLE_NAMES)
            if frozen:
                offenders.append(f"{path.name}: {sorted(frozen)}")
    assert not offenders, (
        f"these modules freeze the palette at import time: {offenders}")


# ── the widgets follow a switch ──────────────────────────────────

def test_an_open_editor_restyles_itself_on_a_switch():
    """The host only calls set_theme — every open editor is already listening,
    so it must repaint without being told."""
    from PySide6.QtWidgets import QApplication, QWidget
    from textli.editor import ZenMarkdownEditor

    app = QApplication.instance() or QApplication([])
    theme.set_theme("light")
    host = QWidget()
    ed = ZenMarkdownEditor(parent=host, text="# Hi\n\nprose\n", title="t.md")
    assert theme.LIGHT.ZEN_MD_BG.name() in ed._editor.styleSheet()

    theme.set_theme("dark")
    app.processEvents()
    assert theme.DARK.ZEN_MD_BG.name() in ed._editor.styleSheet()
    assert theme.DARK.ZEN_MD_BG.name() in ed._rendered.styleSheet()
    ed.deleteLater()
    host.deleteLater()


def test_constructing_with_a_theme_avoids_a_flash_of_the_other_one():
    from PySide6.QtWidgets import QApplication, QWidget
    from textli.editor import ZenMarkdownEditor

    app = QApplication.instance() or QApplication([])
    theme.set_theme("light")
    host = QWidget()
    ed = ZenMarkdownEditor(parent=host, text="# Hi\n", title="t.md",
                           theme_name="dark")
    assert theme.is_dark()
    assert theme.DARK.ZEN_MD_BG.name() in ed._editor.styleSheet()
    ed.deleteLater()
    host.deleteLater()
