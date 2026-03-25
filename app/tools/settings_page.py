"""
SettingsPage — application settings tool.

Sections:
  • Saved Apps  — add / remove package names used across tools
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt

from app.config import AppConfig


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        # Outer scroll so the page works at any window height
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(32)

        # Page title
        title = QLabel("Settings")
        title.setStyleSheet("font-size:24px; font-weight:bold; color:#eef;")
        layout.addWidget(title)

        layout.addWidget(self._make_hsep())
        layout.addWidget(self._build_saved_apps_section())
        layout.addStretch()

    # ── Saved Apps section ────────────────────────────────────────────────────

    def _build_saved_apps_section(self) -> QWidget:
        section = QWidget()
        vl = QVBoxLayout(section)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(16)

        # Section heading
        heading = QLabel("Saved Apps")
        heading.setStyleSheet("font-size:16px; font-weight:bold; color:#dde;")
        vl.addWidget(heading)

        desc = QLabel(
            "Package IDs saved here appear as quick-select options in the "
            "Copy Preferences tool."
        )
        desc.setStyleSheet("color:#667; font-size:12px;")
        desc.setWordWrap(True)
        vl.addWidget(desc)

        # Add-app form
        vl.addWidget(self._build_add_form())

        # Live app list (refreshes on add/remove)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)
        vl.addWidget(self._list_container)

        self._refresh_list()
        return section

    def _build_add_form(self) -> QWidget:
        form = QWidget()
        hl = QHBoxLayout(form)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("Display name  (e.g. My Game)")
        self._name_input.setFixedHeight(34)

        self._pkg_input = QLineEdit()
        self._pkg_input.setPlaceholderText("Package ID  (e.g. com.example.mygame)")
        self._pkg_input.setFixedHeight(34)
        self._pkg_input.setMinimumWidth(240)

        add_btn = QPushButton("+ Add")
        add_btn.setFixedHeight(34)
        add_btn.setFixedWidth(72)
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._add_app)

        self._error_lbl = QLabel("")
        self._error_lbl.setStyleSheet("color:#e05; font-size:11px;")

        hl.addWidget(self._name_input, 1)
        hl.addWidget(self._pkg_input, 2)
        hl.addWidget(add_btn)

        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(4)
        wl.addWidget(form)
        wl.addWidget(self._error_lbl)
        return wrapper

    # ── List management ───────────────────────────────────────────────────────

    def _refresh_list(self):
        # Clear existing rows
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        apps = AppConfig.get_apps()
        if not apps:
            empty = QLabel("No apps saved yet. Add one above.")
            empty.setStyleSheet(
                "color:#334; font-size:12px; font-style:italic; padding:12px 0 4px 0;"
            )
            self._list_layout.addWidget(empty)
            return

        # Column header
        hdr = self._make_list_header()
        self._list_layout.addWidget(hdr)
        self._list_layout.addWidget(self._make_hsep())

        for app in apps:
            self._list_layout.addWidget(self._make_app_row(app["name"], app["package"]))

    def _make_list_header(self) -> QWidget:
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(4, 0, 4, 0)
        hl.setSpacing(12)
        name_hdr = QLabel("Name")
        name_hdr.setStyleSheet("color:#445; font-size:11px; font-weight:bold; letter-spacing:1px;")
        pkg_hdr = QLabel("Package ID")
        pkg_hdr.setStyleSheet("color:#445; font-size:11px; font-weight:bold; letter-spacing:1px;")
        hl.addWidget(name_hdr, 1)
        hl.addWidget(pkg_hdr, 2)
        hl.addSpacing(34)   # room for the delete button
        return row

    def _make_app_row(self, name: str, package: str) -> QWidget:
        row = QWidget()
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setStyleSheet(
            "QWidget { border-radius:6px; padding:2px 0; }"
            "QWidget:hover { background:#0f0f1a; }"
        )
        hl = QHBoxLayout(row)
        hl.setContentsMargins(4, 6, 4, 6)
        hl.setSpacing(12)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("color:#ccd; font-size:13px;")

        pkg_lbl = QLabel(package)
        pkg_lbl.setStyleSheet("color:#7c3aed; font-size:12px;")
        pkg_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(26, 26)
        del_btn.setObjectName("danger")
        del_btn.setToolTip(f"Remove {name}")
        del_btn.clicked.connect(lambda _, p=package: self._remove_app(p))

        hl.addWidget(name_lbl, 1)
        hl.addWidget(pkg_lbl, 2)
        hl.addWidget(del_btn)
        return row

    # ── Actions ───────────────────────────────────────────────────────────────

    def _add_app(self):
        name    = self._name_input.text().strip()
        package = self._pkg_input.text().strip()

        if not name:
            self._error_lbl.setText("Display name is required.")
            self._name_input.setFocus()
            return
        if not package:
            self._error_lbl.setText("Package ID is required.")
            self._pkg_input.setFocus()
            return
        if " " in package:
            self._error_lbl.setText("Package ID must not contain spaces.")
            self._pkg_input.setFocus()
            return

        self._error_lbl.setText("")
        AppConfig.add_app(name, package)
        self._name_input.clear()
        self._pkg_input.clear()
        self._name_input.setFocus()
        self._refresh_list()

    def _remove_app(self, package: str):
        AppConfig.remove_app(package)
        self._refresh_list()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_hsep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("color:#1e1e38;")
        f.setFixedHeight(1)
        return f
