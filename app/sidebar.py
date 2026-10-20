"""
Sidebar navigation: a native source list.

  • add_tool(id, label)               — main tools, top of the list
  • add_tool(id, label, group="...")  — tools inside a collapsible group
                                        (e.g. "Legacy tools"), below the main tools
  • add_pinned(id, label)             — tools listed last (Settings)

The first main tool added is selected automatically.
"""

from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QFrame, QAbstractItemView
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QPalette

SIDEBAR_WIDTH = 200
_ID = Qt.ItemDataRole.UserRole


class SidebarWidget(QTreeWidget):
    tool_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups: dict[str, QTreeWidgetItem] = {}
        self._pinned: list[QTreeWidgetItem] = []
        self._selected_once = False

        self.setHeaderHidden(True)
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setIndentation(14)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        # Sit on the window background like a macOS source list
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, pal.color(QPalette.ColorRole.Window))
        self.setPalette(pal)

        self.currentItemChanged.connect(self._on_current)
        self.itemClicked.connect(self._on_clicked)

    # ── Public API ────────────────────────────────────────────────────────────

    def add_tool(self, tool_id: str, label: str, group: str | None = None):
        item = self._item(tool_id, label)
        if group is None:
            # Main tools go above any group / pinned items
            first_group = min((self.indexOfTopLevelItem(g) for g in [*self._groups.values(), *self._pinned]),
                              default=self.topLevelItemCount())
            self.insertTopLevelItem(first_group, item)
            if not self._selected_once:
                self._selected_once = True
                self.setCurrentItem(item)
        else:
            self._group(group).addChild(item)

    def add_pinned(self, tool_id: str, label: str):
        item = self._item(tool_id, label)
        self.addTopLevelItem(item)
        self._pinned.append(item)

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _item(tool_id, label):
        item = QTreeWidgetItem([label])
        item.setData(0, _ID, tool_id)
        item.setSizeHint(0, QSize(0, 26))
        return item

    def _group(self, name: str) -> QTreeWidgetItem:
        if name not in self._groups:
            g = QTreeWidgetItem([name])
            g.setFlags(Qt.ItemFlag.ItemIsEnabled)
            g.setSizeHint(0, QSize(0, 26))
            g.setForeground(0, self.palette().brush(QPalette.ColorRole.PlaceholderText))
            pos = min((self.indexOfTopLevelItem(p) for p in self._pinned), default=self.topLevelItemCount())
            self.insertTopLevelItem(pos, g)
            self._groups[name] = g
        return self._groups[name]

    def _on_clicked(self, item, _col):
        if item in self._groups.values():
            item.setExpanded(not item.isExpanded())

    def _on_current(self, item, _prev):
        tool_id = item.data(0, _ID) if item else None
        if tool_id:
            self.tool_selected.emit(tool_id)
