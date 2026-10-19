"""
Sidebar navigation: a plain text list in three zones.

  • add_tool(id, label)               — main tools, top of the list
  • add_tool(id, label, group="...")  — tools inside a collapsible group
                                        (e.g. "Legacy tools"), below the main tools
  • add_pinned(id, label)             — fixed bottom strip (Settings)

The first main tool added is selected automatically.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
from PyQt6.QtCore import pyqtSignal, Qt

from app import theme

SIDEBAR_WIDTH = 208


class SidebarWidget(QWidget):
    tool_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: dict[str, QPushButton] = {}
        self._groups: dict[str, tuple[QPushButton, QWidget, QVBoxLayout]] = {}
        self._active: str | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(SIDEBAR_WIDTH)
        self._build()
        self._apply_style()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 14, 10, 10)
        layout.setSpacing(0)

        title = QLabel("App Listing Studio")
        title.setObjectName("sidebarTitle")
        layout.addWidget(title)
        layout.addSpacing(14)

        self._tool_layout = QVBoxLayout()
        self._tool_layout.setSpacing(1)
        layout.addLayout(self._tool_layout)

        self._group_layout = QVBoxLayout()
        self._group_layout.setSpacing(1)
        layout.addLayout(self._group_layout)

        layout.addStretch(1)

        sep = QFrame()
        sep.setObjectName("sidebarSep")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        layout.addSpacing(6)

        self._pinned_layout = QVBoxLayout()
        self._pinned_layout.setSpacing(1)
        layout.addLayout(self._pinned_layout)

    # ── Public API ────────────────────────────────────────────────────────────

    def add_tool(self, tool_id: str, label: str, group: str | None = None):
        btn = self._make_btn(tool_id, label)
        if group is None:
            self._tool_layout.addWidget(btn)
            if self._active is None:
                self._select(tool_id)
        else:
            _, _, body_layout = self._group(group)
            btn.setProperty("nested", True)
            body_layout.addWidget(btn)
        self._items[tool_id] = btn

    def add_pinned(self, tool_id: str, label: str):
        btn = self._make_btn(tool_id, label)
        self._pinned_layout.addWidget(btn)
        self._items[tool_id] = btn

    # ── Internal ──────────────────────────────────────────────────────────────

    def _group(self, name: str):
        if name in self._groups:
            return self._groups[name]

        header = QPushButton()
        header.setObjectName("groupHeader")
        header.setCheckable(True)
        header.setChecked(False)
        header.setFixedHeight(30)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(1)
        body.setVisible(False)

        def _toggle(open_: bool):
            body.setVisible(open_)
            header.setText(f"{'▾' if open_ else '▸'}  {name}")

        header.toggled.connect(_toggle)
        _toggle(False)

        if self._group_layout.count() == 0:
            self._group_layout.addSpacing(14)
        self._group_layout.addWidget(header)
        self._group_layout.addWidget(body)
        self._groups[name] = (header, body, body_layout)
        return self._groups[name]

    def _make_btn(self, tool_id: str, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setObjectName("toolBtn")
        btn.setFixedHeight(30)
        btn.clicked.connect(lambda _checked, tid=tool_id: self._select(tid))
        return btn

    def _select(self, tool_id: str):
        for tid, btn in self._items.items():
            btn.setChecked(tid == tool_id)
        self._active = tool_id
        self.tool_selected.emit(tool_id)

    def _apply_style(self):
        self.setStyleSheet(f"""
            SidebarWidget {{
                background: {theme.BG_SUNKEN};
                border-right: 1px solid {theme.BORDER};
            }}
            QLabel#sidebarTitle {{
                color: {theme.TEXT};
                font-size: 13px;
                font-weight: 600;
                padding-left: 8px;
            }}
            QFrame#sidebarSep {{ background: {theme.BORDER}; border: none; }}
            QPushButton#toolBtn, QPushButton#groupHeader {{
                background: transparent;
                color: {theme.TEXT_2};
                border: none;
                border-radius: 5px;
                text-align: left;
                padding: 0 8px;
                font-size: 13px;
            }}
            QPushButton#toolBtn[nested="true"] {{ padding-left: 22px; }}
            QPushButton#toolBtn:hover, QPushButton#groupHeader:hover {{
                background: {theme.SURFACE};
                color: {theme.TEXT};
            }}
            QPushButton#toolBtn:checked {{
                background: {theme.SURFACE_2};
                color: {theme.TEXT};
            }}
            QPushButton#groupHeader {{ color: {theme.TEXT_3}; font-size: 12px; }}
            QPushButton#groupHeader:checked {{ background: transparent; }}
        """)
