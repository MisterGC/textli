"""Test-wide isolation: settings never touch the user's real preferences.

Editors persist state (font size, column width, typewriter, open history,
per-file positions) — and they also save on teardown (hideEvent), *after*
any per-test monkeypatch has been undone. ``QSettings("textli", "textli")``
uses the platform-native backend, which macOS refuses to redirect, so the
code routes every settings access through ``textli.settings.app_settings``
and this fixture repoints that seam at a throwaway INI file for the whole
session (deliberately never restored — teardown-time writes from dying
widgets stay isolated too).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402

from textli import settings  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def isolated_qsettings(tmp_path_factory):
    path = tmp_path_factory.mktemp("qsettings") / "textli-tests.ini"
    settings.app_settings = (
        lambda: QSettings(str(path), QSettings.Format.IniFormat))
