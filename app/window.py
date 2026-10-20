"""
Outer application shell: sidebar + stacked content area + global log panel.

Layout:
  ┌──────────┬────────────────────────────────────────┐
  │          │                                        │
  │ Sidebar  │   QStackedWidget (tool pages)          │
  │          │                                        │
  ├──────────┴────────────────────────────────────────┤
  │ GlobalLogPanel (collapsible, persists across nav) │
  └───────────────────────────────────────────────────┘

Tools opt in to the global log by exposing a `logged = pyqtSignal(str)`.
register_tool() detects and auto-connects it.
"""

import os
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget, QFrame,
)
from PyQt6.QtGui import QIcon
from app.sidebar import SidebarWidget
from app.log_panel import GlobalLogPanel

APP_VERSION = "1.2.0"

_HERE     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ICON_PATH = os.path.join(_HERE, "assets", "icon.ico")


def set_app_icon(app):
    """Set QApplication icon + Windows taskbar App User Model ID."""
    if os.path.exists(_ICON_PATH):
        app.setWindowIcon(QIcon(_ICON_PATH))
    # Tell Windows to treat this as its own taskbar entry (not group with python.exe)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "AppListingStudio.App"
            )
        except Exception:
            pass


class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("App Listing Studio")
        self.setMinimumSize(1280, 820)
        self.resize(1420, 920)
        if os.path.exists(_ICON_PATH):
            self.setWindowIcon(QIcon(_ICON_PATH))

        self._tool_map: dict[str, int] = {}

        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)

        # Outer: vertical stack — [sidebar+content] / [log panel]
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Content row: sidebar + tool stack
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        self._sidebar = SidebarWidget()
        self._sidebar.tool_selected.connect(self._on_tool_selected)
        content_row.addWidget(self._sidebar)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        content_row.addWidget(sep)

        self._stack = QStackedWidget()
        content_row.addWidget(self._stack, 1)

        outer.addLayout(content_row, 1)

        # Global log panel — always present, spans full width
        self._log_panel = GlobalLogPanel()
        outer.addWidget(self._log_panel)

    # ── Public API ────────────────────────────────────────────────────────────

    def log(self, msg: str):
        """Write a message to the global log panel."""
        self._log_panel.log(msg)

    def register_tool(self, tool_id: str, label: str, widget: QWidget, group: str | None = None):
        """Add a tool to the sidebar — top level, or inside a collapsible group."""
        self._sidebar.add_tool(tool_id, label, group)
        self._register_widget(tool_id, widget)

    def register_pinned(self, tool_id: str, label: str, widget: QWidget):
        """Add a tool pinned to the bottom of the sidebar (e.g. Settings)."""
        self._sidebar.add_pinned(tool_id, label)
        self._register_widget(tool_id, widget)

    def _register_widget(self, tool_id: str, widget: QWidget):
        self._stack.addWidget(widget)
        self._tool_map[tool_id] = self._stack.count() - 1
        if hasattr(widget, "logged"):
            widget.logged.connect(self._log_panel.log)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_tool_selected(self, tool_id: str):
        if tool_id in self._tool_map:
            self._stack.setCurrentIndex(self._tool_map[tool_id])
