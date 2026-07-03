"""The one place textli opens its settings store.

Everything the editor persists — font size, column width, typewriter,
open-file history, per-file positions — goes through :func:`app_settings`.
That single seam lets the test suite point the store at a throwaway file
(see ``tests/conftest.py``): ``QSettings("textli", "textli")`` always uses
the platform-native backend, which on macOS cannot be redirected, so
scattering that constructor around would make user-settings pollution from
tests unavoidable.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings


def app_settings() -> QSettings:
    return QSettings("textli", "textli")
