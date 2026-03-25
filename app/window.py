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
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
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
        self.setWindowTitle(f"App Listing Studio v{APP_VERSION}")
        self.setMinimumSize(1280, 820)
        self.resize(1420, 920)
        if os.path.exists(_ICON_PATH):
            self.setWindowIcon(QIcon(_ICON_PATH))

        self._tool_map: dict[str, int] = {}

        self._apply_theme()
        self._build()

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #0f0f1a; color: #dde; }

            QGroupBox {
                border: 1px solid #2a2a4a;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px 8px 8px 8px;
                font-weight: bold;
                color: #aab;
                font-size: 11px;
                letter-spacing: 1px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }

            QPushButton {
                background: #1e1e34;
                color: #dde;
                border: 1px solid #3a3a5a;
                border-radius: 7px;
                padding: 7px 16px;
                font-size: 13px;
            }
            QPushButton:hover  { background: #2a2a48; border-color: #6060aa; }
            QPushButton:pressed { background: #16163a; }

            QPushButton#primary {
                background: #3d1065;
                border-color: #7c3aed;
                font-weight: bold;
                font-size: 14px;
                padding: 10px 20px;
            }
            QPushButton#primary:hover { background: #5a18a0; }

            QPushButton#danger { background: #3a0d0d; border-color: #aa3333; }
            QPushButton#danger:hover { background: #5a1515; }

            QLineEdit, QTextEdit {
                background: #16162a;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                padding: 6px 10px;
                color: #eef;
                font-size: 13px;
            }
            QLineEdit:focus, QTextEdit:focus { border-color: #7c3aed; }

            QComboBox {
                background: #16162a;
                border: 1px solid #2a2a4a;
                border-radius: 6px;
                padding: 5px 10px;
                color: #eef;
                font-size: 13px;
            }
            QComboBox::drop-down { border: none; width: 24px; }
            QComboBox QAbstractItemView {
                background: #1e1e34;
                color: #eef;
                selection-background-color: #3d1065;
            }

            QSlider::groove:horizontal { height: 4px; background: #2a2a4a; border-radius: 2px; }
            QSlider::handle:horizontal {
                background: #7c3aed; width: 16px; height: 16px;
                margin: -6px 0; border-radius: 8px;
            }
            QSlider::sub-page:horizontal { background: #7c3aed; border-radius: 2px; }

            QLabel { color: #bbc; }
            QLabel#section { color: #8890aa; font-size: 11px; letter-spacing: 1px; font-weight: bold; }

            QScrollArea { border: none; }
            QScrollBar:vertical { background: #0f0f1a; width: 8px; }
            QScrollBar::handle:vertical { background: #2a2a4a; border-radius: 4px; min-height: 30px; }

            QSpinBox {
                background: #16162a; border: 1px solid #2a2a4a;
                border-radius: 6px; padding: 4px 8px; color: #eef; font-size: 13px;
            }

            QProgressBar {
                background: #1a1a2e; border: 1px solid #2a2a4a;
                border-radius: 4px; text-align: center; color: #aab; font-size: 11px;
            }
            QProgressBar::chunk { background: #7c3aed; border-radius: 3px; }
        """)

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

    def register_tool(self, tool_id: str, icon: str, label: str, widget: QWidget):
        """Add a tool button to the main sidebar area."""
        self._sidebar.add_tool(tool_id, icon, label)
        self._register_widget(tool_id, widget)

    def register_pinned(self, tool_id: str, icon: str, label: str, widget: QWidget):
        """Add a tool button pinned to the bottom of the sidebar (e.g. Settings)."""
        self._sidebar.add_pinned(tool_id, icon, label)
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
