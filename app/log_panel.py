"""
GlobalLogPanel — persistent bottom log strip.

Layout:
  ┌─────────────────────────────────────────────────────────┐
  │ [last message text ...]                     ▲ Log  [✕] │  ← toggle bar (always visible)
  ├─────────────────────────────────────────────────────────┤
  │ [08:01:23] Device scan started                          │
  │ [08:01:24] Found 2 device(s)                            │  ← log area (animated)
  │ ...                                                     │
  └─────────────────────────────────────────────────────────┘
"""

from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFrame,
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

LOG_EXPANDED_H = 170
ANIM_MS = 200


class GlobalLogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._build()
        self._build_animation()
        self._apply_style()

    # ── Public API ────────────────────────────────────────────────────────────

    def log(self, msg: str):
        """Append a timestamped line to the log."""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}]  {msg}"

        # Update the last-message preview in the toggle bar
        preview = msg if len(msg) <= 80 else msg[:77] + "…"
        self._last_msg.setText(preview)

        # Append to the scrolling log
        self._log_edit.append(line)
        self._log_edit.verticalScrollBar().setValue(
            self._log_edit.verticalScrollBar().maximum()
        )

    def toggle(self):
        if self._expanded:
            self._collapse()
        else:
            self._expand()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top border line
        top_sep = QFrame()
        top_sep.setFrameShape(QFrame.Shape.HLine)
        top_sep.setObjectName("logSep")
        top_sep.setFixedHeight(1)
        root.addWidget(top_sep)

        # Toggle bar
        bar = QWidget()
        bar.setObjectName("logBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setFixedHeight(28)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(12, 0, 8, 0)
        bar_layout.setSpacing(8)

        log_icon = QLabel("≡")
        log_icon.setObjectName("logIcon")
        bar_layout.addWidget(log_icon)

        self._last_msg = QLabel("No log entries yet.")
        self._last_msg.setObjectName("logLastMsg")
        self._last_msg.setSizePolicy(
            self._last_msg.sizePolicy().horizontalPolicy(),
            self._last_msg.sizePolicy().verticalPolicy(),
        )
        bar_layout.addWidget(self._last_msg, 1)

        self._toggle_btn = QPushButton("▲  Log")
        self._toggle_btn.setObjectName("logToggleBtn")
        self._toggle_btn.setFixedHeight(22)
        self._toggle_btn.clicked.connect(self.toggle)
        bar_layout.addWidget(self._toggle_btn)

        clear_btn = QPushButton("✕")
        clear_btn.setObjectName("logClearBtn")
        clear_btn.setFixedSize(22, 22)
        clear_btn.setToolTip("Clear log")
        clear_btn.clicked.connect(self._clear)
        bar_layout.addWidget(clear_btn)

        root.addWidget(bar)

        # Log text area (height animated)
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setObjectName("logEdit")
        f = QFont("Consolas", 10)
        f.setStyleHint(QFont.StyleHint.Monospace)
        self._log_edit.setFont(f)
        self._log_edit.setMaximumHeight(0)   # collapsed by default
        root.addWidget(self._log_edit)

    def _build_animation(self):
        self._anim = QPropertyAnimation(self._log_edit, b"maximumHeight")
        self._anim.setDuration(ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    # ── Expand / collapse ─────────────────────────────────────────────────────

    def _expand(self):
        self._expanded = True
        self._toggle_btn.setText("▼  Log")
        self._anim.setStartValue(self._log_edit.maximumHeight())
        self._anim.setEndValue(LOG_EXPANDED_H)
        self._anim.start()

    def _collapse(self):
        self._expanded = False
        self._toggle_btn.setText("▲  Log")
        self._anim.setStartValue(self._log_edit.maximumHeight())
        self._anim.setEndValue(0)
        self._anim.start()

    def _clear(self):
        self._log_edit.clear()
        self._last_msg.setText("Log cleared.")

    # ── Style ─────────────────────────────────────────────────────────────────

    def _apply_style(self):
        self.setStyleSheet("""
            GlobalLogPanel {
                background: #080810;
            }
            QFrame#logSep {
                background: #1a1a2e;
                border: none;
            }
            QWidget#logBar {
                background: #080810;
            }
            QLabel#logIcon {
                color: #334;
                font-size: 14px;
            }
            QLabel#logLastMsg {
                color: #445;
                font-size: 11px;
            }
            QPushButton#logToggleBtn {
                background: #0f0f1a;
                color: #556;
                border: 1px solid #1a1a2e;
                border-radius: 4px;
                font-size: 10px;
                padding: 0 8px;
            }
            QPushButton#logToggleBtn:hover {
                background: #14142a;
                color: #889;
                border-color: #2a2a4a;
            }
            QPushButton#logClearBtn {
                background: transparent;
                color: #334;
                border: none;
                border-radius: 4px;
                font-size: 10px;
                padding: 0;
            }
            QPushButton#logClearBtn:hover {
                background: #1a1a2e;
                color: #667;
            }
            QTextEdit#logEdit {
                background: #050508;
                color: #5a8a5a;
                border: none;
                border-top: 1px solid #1a1a2e;
                padding: 6px 12px;
            }
        """)
