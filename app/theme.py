"""
Native look helpers.

The app uses the platform's own widget style (macOS, Windows 11, or Fusion on
Linux) and follows the system's light/dark setting, so there is no application
stylesheet. Use these helpers for the few things the platform doesn't provide:
secondary text, headings and status colours.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication, QPalette, QFont, QColor
from PyQt6.QtWidgets import QWidget

ERROR = "error"
WARN = "warn"     # same values as app.checks
OK = "ok"

# System colours (Apple HIG values; close to Fluent's on Windows)
_LEVEL_RGB = {
    ERROR: ("#d70015", "#ff453a"),
    WARN:  ("#a05a00", "#ff9f0a"),
    OK:    ("#248a3d", "#30d158"),
}

MONO_FONT = "Menlo, Consolas, 'DejaVu Sans Mono', monospace"


def is_dark() -> bool:
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def level_color(level: str) -> str:
    light, dark = _LEVEL_RGB[level]
    return dark if is_dark() else light


def muted(w: QWidget) -> QWidget:
    """Secondary text: the platform's placeholder/secondary label colour."""
    w.setForegroundRole(QPalette.ColorRole.PlaceholderText)
    return w


def heading(w: QWidget, delta: float = 2) -> QWidget:
    """Bold, slightly larger than the system font."""
    f = QFont(w.font())
    f.setPointSizeF(f.pointSizeF() + delta)
    f.setWeight(QFont.Weight.DemiBold)
    w.setFont(f)
    return w


def small(w: QWidget, delta: float = -1) -> QWidget:
    f = QFont(w.font())
    f.setPointSizeF(f.pointSizeF() + delta)
    w.setFont(f)
    return w


def status(w: QWidget, level: str | None) -> QWidget:
    """Colour a label for ERROR / WARN / OK; None resets to normal text."""
    pal = w.palette()
    if level is None:
        pal = QGuiApplication.palette()
    else:
        pal.setColor(QPalette.ColorRole.WindowText, QColor(level_color(level)))
    w.setForegroundRole(QPalette.ColorRole.WindowText)
    w.setPalette(pal)
    return w
