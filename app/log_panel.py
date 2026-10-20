"""
GlobalLogPanel — persistent bottom log strip.

Layout:
  ┌─────────────────────────────────────────────────────────┐
  │ last message text ...                    [Show Log] [Clear] │  ← always visible
  ├─────────────────────────────────────────────────────────┤
  │ 08:01:23  Device scan started                           │
  │ 08:01:24  Found 2 device(s)                             │  ← shown on demand
  └─────────────────────────────────────────────────────────┘
"""

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QFrame,
)
from PyQt6.QtGui import QFontDatabase

from app import theme

LOG_EXPANDED_H = 170


class GlobalLogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    # ── Public API ────────────────────────────────────────────────────────────

    def log(self, msg: str):
        """Append a timestamped line to the log."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._last_msg.setText(msg if len(msg) <= 100 else msg[:97] + "…")
        self._log_edit.appendPlainText(f"{ts}  {msg}")

    def toggle(self):
        show = not self._log_edit.isVisible()
        self._log_edit.setVisible(show)
        self._toggle_btn.setText("Hide Log" if show else "Show Log")

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        bar = QHBoxLayout()
        bar.setContentsMargins(12, 4, 8, 4)
        bar.setSpacing(6)
        self._last_msg = theme.small(theme.muted(QLabel("No log entries yet.")))
        bar.addWidget(self._last_msg, 1)

        self._toggle_btn = QPushButton("Show Log")
        self._toggle_btn.setFlat(True)
        self._toggle_btn.clicked.connect(self.toggle)
        bar.addWidget(self._toggle_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setFlat(True)
        clear_btn.clicked.connect(self._clear)
        bar.addWidget(clear_btn)
        root.addLayout(bar)

        self._log_edit = QPlainTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFrameShape(QFrame.Shape.NoFrame)
        f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        f.setPointSizeF(f.pointSizeF() - 1)
        self._log_edit.setFont(f)
        self._log_edit.setFixedHeight(LOG_EXPANDED_H)
        self._log_edit.setVisible(False)
        root.addWidget(self._log_edit)

    def _clear(self):
        self._log_edit.clear()
        self._last_msg.setText("Log cleared.")
