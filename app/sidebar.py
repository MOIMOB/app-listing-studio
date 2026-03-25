"""
Animated collapsible sidebar navigation widget.
Expanded (default): 220px — icon + label.
Collapsed: 52px  — icon only.

Two button zones:
  • add_tool()   — scrollable main area (tools)
  • add_pinned() — fixed bottom strip (settings, etc.), above the toggle
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFrame,
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QFont

SIDEBAR_EXPANDED  = 220
SIDEBAR_COLLAPSED = 52
ANIM_MS = 220


class SidebarWidget(QWidget):
    tool_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = True
        # All registered items regardless of zone
        self._items: dict[str, tuple[QPushButton, str, str]] = {}
        self._active: str | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(SIDEBAR_EXPANDED)

        self._build()
        self._build_animations()
        self._apply_style()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hdr.setObjectName("sidebarHeader")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(10, 0, 8, 0)
        hl.setSpacing(8)

        logo = QLabel("🎬")
        lf = QFont()
        lf.setPointSize(16)
        logo.setFont(lf)
        logo.setFixedSize(32, 32)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._app_name_lbl = QLabel("App Studio")
        nf = QFont()
        nf.setPointSize(10)
        nf.setBold(True)
        self._app_name_lbl.setFont(nf)
        self._app_name_lbl.setObjectName("sidebarTitle")

        hl.addWidget(logo)
        hl.addWidget(self._app_name_lbl, 1)
        layout.addWidget(hdr)
        layout.addWidget(self._make_sep())

        # ── Main tool area (flexible) ─────────────────────────────────────────
        self._tool_area = QWidget()
        self._tool_area.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._tool_layout = QVBoxLayout(self._tool_area)
        self._tool_layout.setContentsMargins(6, 8, 6, 8)
        self._tool_layout.setSpacing(3)
        self._tool_layout.addStretch()
        layout.addWidget(self._tool_area, 1)

        # ── Pinned bottom area (settings etc.) ────────────────────────────────
        layout.addWidget(self._make_sep())

        self._pinned_area = QWidget()
        self._pinned_area.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._pinned_layout = QVBoxLayout(self._pinned_area)
        self._pinned_layout.setContentsMargins(6, 4, 6, 4)
        self._pinned_layout.setSpacing(3)
        layout.addWidget(self._pinned_area)

        # ── Toggle ────────────────────────────────────────────────────────────
        layout.addWidget(self._make_sep())
        self._toggle = QPushButton("◀")
        self._toggle.setObjectName("sidebarToggle")
        self._toggle.setFixedHeight(38)
        self._toggle.setToolTip("Collapse sidebar")
        self._toggle.clicked.connect(self.toggle)
        layout.addWidget(self._toggle)

    def _make_sep(self):
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setObjectName("sidebarSep")
        f.setFixedHeight(1)
        return f

    def _build_animations(self):
        self._anim_min = QPropertyAnimation(self, b"minimumWidth")
        self._anim_min.setDuration(ANIM_MS)
        self._anim_min.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._anim_max = QPropertyAnimation(self, b"maximumWidth")
        self._anim_max.setDuration(ANIM_MS)
        self._anim_max.setEasingCurve(QEasingCurve.Type.InOutCubic)

    # ── Public API ────────────────────────────────────────────────────────────

    def add_tool(self, tool_id: str, icon: str, label: str):
        """Add a tool button to the main (scrollable) area. First added is auto-selected."""
        btn = self._make_btn(tool_id, icon, label)
        pos = self._tool_layout.count() - 1   # before trailing stretch
        self._tool_layout.insertWidget(pos, btn)
        self._items[tool_id] = (btn, icon, label)
        if self._active is None:
            self._select(tool_id)

    def add_pinned(self, tool_id: str, icon: str, label: str):
        """Add a button pinned to the bottom strip (e.g. Settings)."""
        btn = self._make_btn(tool_id, icon, label)
        self._pinned_layout.addWidget(btn)
        self._items[tool_id] = (btn, icon, label)
        # Pinned items never auto-select

    # ── Internal ──────────────────────────────────────────────────────────────

    def _make_btn(self, tool_id: str, icon: str, label: str) -> QPushButton:
        btn = QPushButton(f"  {icon}   {label}")
        btn.setCheckable(True)
        btn.setObjectName("toolBtn")
        btn.setFixedHeight(40)
        btn.setToolTip(label)
        btn.clicked.connect(lambda _checked, tid=tool_id: self._select(tid))
        return btn

    def _select(self, tool_id: str):
        for tid, (btn, _, _) in self._items.items():
            btn.setChecked(tid == tool_id)
        self._active = tool_id
        self.tool_selected.emit(tool_id)

    def toggle(self):
        if self._expanded:
            self._collapse()
        else:
            self._expand()

    def _expand(self):
        self._expanded = True
        self._animate(SIDEBAR_COLLAPSED, SIDEBAR_EXPANDED)
        self._toggle.setText("◀")
        self._toggle.setToolTip("Collapse sidebar")
        self._app_name_lbl.setVisible(True)
        for _, (btn, icon, label) in self._items.items():
            btn.setText(f"  {icon}   {label}")

    def _collapse(self):
        self._expanded = False
        self._animate(SIDEBAR_EXPANDED, SIDEBAR_COLLAPSED)
        self._toggle.setText("▶")
        self._toggle.setToolTip("Expand sidebar")
        self._app_name_lbl.setVisible(False)
        for _, (btn, icon, _) in self._items.items():
            btn.setText(icon)

    def _animate(self, start: int, end: int):
        for anim in (self._anim_min, self._anim_max):
            anim.setStartValue(start)
            anim.setEndValue(end)
            anim.start()

    def _apply_style(self):
        self.setStyleSheet("""
            SidebarWidget {
                background: #0a0a14;
                border-right: 1px solid #1a1a2e;
            }
            QWidget#sidebarHeader {
                background: #0a0a14;
            }
            QLabel#sidebarTitle {
                color: #bbc;
            }
            QFrame#sidebarSep {
                background: #1a1a2e;
                border: none;
            }
            QPushButton#toolBtn {
                background: transparent;
                color: #99a;
                border: none;
                border-radius: 8px;
                text-align: left;
                font-size: 13px;
                padding: 0 8px;
            }
            QPushButton#toolBtn:hover {
                background: #14142a;
                color: #ccd;
            }
            QPushButton#toolBtn:checked {
                background: #1e1e38;
                color: #eef;
                font-weight: bold;
            }
            QPushButton#toolBtn:checked:hover {
                background: #242448;
            }
            QPushButton#sidebarToggle {
                background: #0a0a14;
                color: #445;
                border: none;
                border-radius: 0px;
                font-size: 11px;
            }
            QPushButton#sidebarToggle:hover {
                background: #0f0f1a;
                color: #778;
            }
        """)
