"""Bundled fonts reach embedding hosts (#25): the public editor widgets
register the bundled faces on construction — not just the standalone app.py
path — so an embedded editor renders comments in Caveat like the standalone one.
Registration is idempotent, so repeated construction and app.py's own call are
harmless."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

import textli.editor as editor  # noqa: E402
import textli.fonts as fonts  # noqa: E402
import textli.inline_editor as inline  # noqa: E402


def test_registration_makes_caveat_available():
    QApplication.instance() or QApplication([])
    fonts.register_bundled_fonts()
    assert "Caveat" in QFontDatabase.families()


def test_registration_is_idempotent(monkeypatch):
    calls: list = []

    class _Stub:
        @staticmethod
        def addApplicationFont(path):
            calls.append(path)
            return 0

    monkeypatch.setattr(fonts, "QFontDatabase", _Stub)
    monkeypatch.setattr(fonts, "_registered", False)
    fonts.register_bundled_fonts()
    first = len(calls)
    assert first >= 1                       # loaded the bundled files once
    fonts.register_bundled_fonts()          # a second call short-circuits
    assert len(calls) == first


def test_zen_editor_registers_fonts_on_construction(monkeypatch):
    QApplication.instance() or QApplication([])
    called: list = []
    monkeypatch.setattr(editor, "register_bundled_fonts",
                        lambda: called.append(True))
    parent = QWidget()
    editor.ZenMarkdownEditor(parent, "hello", title="T")
    assert called, "constructing the editor registered the bundled fonts"


def test_inline_editor_registers_fonts_on_construction(monkeypatch):
    QApplication.instance() or QApplication([])
    called: list = []
    monkeypatch.setattr(inline, "register_bundled_fonts",
                        lambda: called.append(True))
    inline.InlineVimEditor("hello")
    assert called, "constructing the inline editor registered the bundled fonts"
