"""
Store Preview — the main view.

Left: "My listings" — app repos (folders with fastlane/ and/or plan JSONs) and loose plan files,
saved in the app config. Right: the selected listing as a mock Google Play / App Store page.

A repo can be shown from its fastlane "Store files" (the images that get uploaded) or from any
plan JSON in it (rendered from raw captures). Shown files are watched: save in your editor
or drop new screenshots in and the preview updates.

Thumbnail click → full-size view with arrow-key navigation.
"""

import io
import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QListWidget,
    QListWidgetItem, QScrollArea, QFrame, QFileDialog, QCheckBox, QButtonGroup,
    QSizePolicy, QMenu,
)
from PyQt6.QtCore import Qt, QThread, QTimer, QFileSystemWatcher, QRectF, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QFont, QCursor, QIcon

from PIL import Image

from app.config import AppConfig
from app.listing import Entry, PlanSource, find_plans, load_preview_image, aspect_of
from app.plan import _ROOT
from app.tools.config_viewer_panel import _FullViewDialog

_RENDER_W = 540     # preview render width; full canvas is only needed for export
_PAGE_W = 412       # mobile store page width (dp-ish)

# Light / dark palettes for the two stores
_THEMES = {
    ("android", False): dict(bg="#ffffff", text="#1f1f1f", sub="#5f6368", accent="#01875f",
                             btn_text="#ffffff", divider="#e8eaed"),
    ("android", True):  dict(bg="#131314", text="#e3e3e3", sub="#9aa0a6", accent="#a8dab5",
                             btn_text="#0b3d23", divider="#2e2f31"),
    ("ios", False):     dict(bg="#ffffff", text="#000000", sub="#8a8a8e", accent="#007aff",
                             btn_text="#ffffff", divider="#e5e5ea"),
    ("ios", True):      dict(bg="#000000", text="#ffffff", sub="#8d8d93", accent="#0a84ff",
                             btn_text="#ffffff", divider="#38383a"),
}


def _rounded_pixmap(img: Image.Image, w: int, h: int, radius: int) -> QPixmap:
    """PIL image → QPixmap of w×h with rounded corners (call on the GUI thread)."""
    buf = io.BytesIO()
    img.resize((w, h), Image.LANCZOS).save(buf, format="PNG")
    src = QPixmap()
    src.loadFromData(buf.getvalue())
    out = QPixmap(w, h)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, src)
    p.end()
    return out


def _letter_icon(name: str, size: int, radius: int, color: str) -> QPixmap:
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.fillPath(path, QColor(color))
    f = QFont()
    f.setPixelSize(int(size * 0.45))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#ffffff"))
    p.drawText(out.rect(), Qt.AlignmentFlag.AlignCenter, (name[:1] or "?").upper())
    p.end()
    return out


def _app_icon(path, name, size):
    radius = int(size * 0.225)
    if path and os.path.exists(path):
        try:
            return _rounded_pixmap(Image.open(path).convert("RGBA"), size, size, radius)
        except Exception:
            pass
    return _letter_icon(name, size, radius, "#5e9cff")


# ─── Background render ────────────────────────────────────────────────────────

class _RenderWorker(QThread):
    done = pyqtSignal(int, object, object)   # generation, cache key, PIL image | None

    def __init__(self, generation, jobs):
        super().__init__()
        self._gen = generation
        self._jobs = jobs   # [(key, path, compose_kwargs | None)]
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for key, path, kwargs in self._jobs:
            if self._stop:
                return
            try:
                img = load_preview_image(path, kwargs, _RENDER_W)
            except Exception:
                img = None
            self.done.emit(self._gen, key, img)


class _Thumb(QLabel):
    clicked = pyqtSignal(int)

    def __init__(self, idx, w, h):
        super().__init__("")
        self._idx = idx
        self.setFixedSize(w, h)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._idx)


# ─── Panel ────────────────────────────────────────────────────────────────────

class StorePreviewPanel(QWidget):
    logged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._entries: list[Entry] = []
        self._entry: Entry | None = None
        self._source = None
        self._source_error = ""
        self._platform = "android"
        self._cache = {}          # (platform, device, idx) → PIL image
        self._generation = 0
        self._worker = None
        self._stale_workers = []  # stopped workers kept alive until their thread exits
        self._thumbs = []
        self._shots = []

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._on_file_changed)
        self._watcher.directoryChanged.connect(self._on_file_changed)
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(300)   # editors write in bursts; also lets atomic saves land
        self._reload_timer.timeout.connect(self._reload)

        self._build()

        # --plan on the command line adds that plan and opens it
        cli = sys.argv[sys.argv.index("--plan") + 1] if "--plan" in sys.argv[:-1] else ""
        if cli and os.path.exists(cli):
            AppConfig.add_listing(os.path.abspath(cli))
        QTimer.singleShot(0, lambda: self._load_entries(os.path.abspath(cli) if cli else AppConfig.get_last_plan()))

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_listings_column())

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self._build_toolbar())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget()
        self._holder_lay = QHBoxLayout(holder)
        self._holder_lay.setContentsMargins(24, 24, 24, 24)
        self._scroll.setWidget(holder)
        right.addWidget(self._scroll, 1)
        root.addLayout(right, 1)

    def _build_listings_column(self):
        col = QWidget()
        col.setFixedWidth(250)
        col.setStyleSheet("background:#0c0c16; border-right:1px solid #2a2a2d;")
        lay = QVBoxLayout(col)
        lay.setContentsMargins(10, 12, 10, 10)
        lay.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("My listings")
        title.setStyleSheet("color:#ececec; font-size:13px; font-weight:600; border:none;")
        head.addWidget(title, 1)
        add_btn = QPushButton("+")
        add_btn.setFixedSize(30, 28)
        add_btn.setToolTip("Add a repo or plan")
        menu = QMenu(add_btn)
        menu.addAction("Add app repo folder…", self._add_repo)
        menu.addAction("Add plan JSON file…", self._add_plan_file)
        menu.addAction("Scan folder for repos…", self._scan_folder)
        add_btn.setMenu(menu)
        add_btn.setStyleSheet("QPushButton::menu-indicator { width:0; }")
        head.addWidget(add_btn)
        self._remove_btn = QPushButton("✕")
        self._remove_btn.setFixedSize(30, 28)
        self._remove_btn.setToolTip("Remove from My listings (files are not touched)")
        self._remove_btn.clicked.connect(self._remove_selected)
        head.addWidget(self._remove_btn)
        lay.addLayout(head)

        self._list = QListWidget()
        self._list.setIconSize(QSize(36, 36))
        self._list.setStyleSheet("""
            QListWidget { background:transparent; border:none; outline:none; }
            QListWidget::item { color:#d0d0d4; padding:6px 4px; border-radius:8px; }
            QListWidget::item:hover { background:#1f1f21; }
            QListWidget::item:selected { background:#262629; color:#fff; }
        """)
        self._list.currentRowChanged.connect(self._on_entry_selected)
        lay.addWidget(self._list, 1)
        return col

    def _build_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet("background:#1b1b1d; border-bottom:1px solid #323236;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 8, 16, 8)
        bl.setSpacing(10)

        self._source_combo = QComboBox()
        self._source_combo.setMinimumWidth(190)
        self._source_combo.setToolTip("Store files = the images in fastlane; plans are rendered from raw captures")
        self._source_combo.currentIndexChanged.connect(self._on_source_selected)
        bl.addWidget(self._source_combo)

        self._store_group = QButtonGroup(self)
        for key, label in (("android", "Google Play"), ("ios", "App Store")):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(key == "android")
            b.setObjectName("chip")
            b.clicked.connect(lambda _c, k=key: self._set_platform(k))
            self._store_group.addButton(b)
            bl.addWidget(b)

        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(150)
        self._device_combo.currentIndexChanged.connect(lambda _i: self._rebuild_page())
        bl.addWidget(self._device_combo)

        self._locale_combo = QComboBox()
        self._locale_combo.setToolTip("Language")
        self._locale_combo.currentTextChanged.connect(self._set_locale)
        bl.addWidget(self._locale_combo)

        self._dark_cb = QCheckBox("Dark")
        self._dark_cb.toggled.connect(lambda _on: self._rebuild_page())
        bl.addWidget(self._dark_cb)

        self._status = QLabel("")
        self._status.setStyleSheet("color:#8e8e93; font-size:12px;")
        self._status.setWordWrap(True)
        bl.addWidget(self._status, 1)
        return bar

    # ── My listings ───────────────────────────────────────────────────────────

    def _load_entries(self, select_path=""):
        self._entries = [Entry(p) for p in AppConfig.get_listings()]
        self._list.blockSignals(True)
        self._list.clear()
        for e in self._entries:
            if e.exists():
                sources = e.sources()
                store = next((p for k, p in sources if k == "store"), "")
                icon_path = os.path.join(store, "metadata", "android", "en-US", "images", "icon.png") if store else ""
                text, sub = e.name, e.summary()
            else:
                icon_path, text, sub = "", e.name, "missing — moved or deleted?"
            item = QListWidgetItem(QIcon(_app_icon(icon_path, e.name, 72)), f"{text}\n{sub}")
            item.setToolTip(e.path)
            item.setSizeHint(QSize(0, 50))
            self._list.addItem(item)
        self._list.blockSignals(False)
        self._remove_btn.setEnabled(bool(self._entries))

        paths = [e.path for e in self._entries]
        row = paths.index(select_path) if select_path in paths else (0 if paths else -1)
        if row >= 0:
            self._list.setCurrentRow(row)
            self._on_entry_selected(row)
        else:
            self._entry = self._source = None
            self._rebuild_page()

    def _add_paths(self, paths):
        for p in paths:
            AppConfig.add_listing(os.path.abspath(p))
        if paths:
            self._load_entries(os.path.abspath(paths[0]))
            self.logged.emit(f"My listings: added {len(paths)}")

    def _add_repo(self):
        d = QFileDialog.getExistingDirectory(self, "App Repo Folder", self._browse_start())
        if d:
            self._add_paths([d])

    def _add_plan_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Plan JSON", self._browse_start(), "JSON (*.json)")
        if path:
            self._add_paths([path])

    def _scan_folder(self):
        """Add every direct subfolder that has fastlane/ or a plan JSON."""
        d = QFileDialog.getExistingDirectory(self, "Folder With Repos", self._browse_start())
        if not d:
            return
        known = set(AppConfig.get_listings())
        found = []
        for name in sorted(os.listdir(d)):
            sub = os.path.abspath(os.path.join(d, name))
            if not os.path.isdir(sub) or sub in known:
                continue
            if os.path.isdir(os.path.join(sub, "fastlane")) or find_plans(sub, max_depth=3):
                found.append(sub)
        if found:
            self._add_paths(found)
        else:
            self.logged.emit(f"My listings: no new repos with fastlane/ or a plan in {d}")

    def _browse_start(self):
        return os.path.dirname(self._entry.root) if self._entry else os.path.expanduser("~")

    def _remove_selected(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._entries):
            AppConfig.remove_listing(self._entries[row].path)
            self._load_entries()

    def _on_entry_selected(self, row):
        if not (0 <= row < len(self._entries)):
            return
        self._entry = self._entries[row]
        AppConfig.set_last_plan(self._entry.path)
        self._source_combo.blockSignals(True)
        self._source_combo.clear()
        if self._entry.exists():
            for kind, path in self._entry.sources():
                label = "Store files (fastlane)" if kind == "store" else f"Plan: {os.path.relpath(path, self._entry.root)}"
                self._source_combo.addItem(label, (kind, path))
        self._source_combo.blockSignals(False)
        self._source_combo.setVisible(self._source_combo.count() > 1)
        self._on_source_selected(0)

    def _on_source_selected(self, idx):
        data = self._source_combo.itemData(idx) if idx >= 0 else None
        self._cache = {}
        self._source_error = ""
        self._source = None
        if data:
            try:
                self._source = self._entry.open_source(*data)
            except Exception as e:
                self._source_error = str(e)
            if self._source:
                self.logged.emit(f"Store Preview: {self._entry.name} — {self._source.label}")
                # Start on a store that actually has screenshots
                if not self._source.devices(self._platform):
                    other = "ios" if self._platform == "android" else "android"
                    if self._source.devices(other):
                        self._platform = other
        self._sync_store_buttons()
        self._fill_locales()
        self._fill_devices()
        self._watch()

    # ── Watching ──────────────────────────────────────────────────────────────

    def _watch(self):
        # Editors that save atomically replace the file, which drops it from the watcher
        old = self._watcher.files() + self._watcher.directories()
        if old:
            self._watcher.removePaths(old)
        paths = self._source.watch_paths() if self._source else []
        if isinstance(self._source, PlanSource) or (self._entry and self._entry.is_file):
            paths = sorted(set(paths) | {self._entry.path if self._entry.is_file else self._source.path})
        if paths:
            self._watcher.addPaths([p for p in paths if os.path.exists(p)])

    def _on_file_changed(self, _path):
        self._reload_timer.start()

    def _reload(self):
        if not self._source:
            return
        try:
            if isinstance(self._source, PlanSource):
                self._source.reload()
            else:
                locale = self._source.locale
                self._source = self._entry.open_source("store", self._source.fastlane)
                self._source.locale = locale if locale in self._source.locales else self._source.locale
            self._source_error = ""
        except Exception as e:
            # Keep the last good preview while the file is mid-edit / invalid
            self._set_status(f"⚠ {os.path.basename(getattr(self._source, 'path', ''))}: {e}", error=True)
            self._watch()
            return
        self._cache = {}
        self.logged.emit(f"Store Preview: reloaded {self._entry.name}")
        self._fill_locales()
        self._fill_devices()
        self._watch()

    # ── Store / locale / device ───────────────────────────────────────────────

    def _sync_store_buttons(self):
        for b in self._store_group.buttons():
            b.setChecked((b.text() == "Google Play") == (self._platform == "android"))

    def _set_platform(self, platform):
        self._platform = platform
        self._sync_store_buttons()
        self._fill_devices()

    def _fill_locales(self):
        locales = self._source.locales if self._source else []
        self._locale_combo.blockSignals(True)
        self._locale_combo.clear()
        self._locale_combo.addItems(locales)
        if self._source:
            self._locale_combo.setCurrentText(self._source.locale)
        self._locale_combo.setVisible(len(locales) > 1)
        self._locale_combo.blockSignals(False)

    def _set_locale(self, locale):
        if not self._source or not locale or locale == self._source.locale:
            return
        self._source.locale = locale
        if isinstance(self._source, PlanSource):
            try:
                self._source.reload()
            except Exception as e:
                self._set_status(f"{e}", error=True)
                return
        self._cache = {}
        self._fill_devices()
        self._watch()

    def _fill_devices(self):
        prev = self._device_combo.currentText()
        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        if self._source:
            self._device_combo.addItems(self._source.devices(self._platform))
        idx = self._device_combo.findText(prev)
        self._device_combo.setCurrentIndex(max(idx, 0))
        self._device_combo.blockSignals(False)
        self._rebuild_page()

    # ── Page ──────────────────────────────────────────────────────────────────

    def _set_status(self, text, error=False, tooltip=""):
        self._status.setText(text)
        self._status.setToolTip(tooltip)
        self._status.setStyleSheet(f"color:{'#ff8866' if error else '#8e8e93'}; font-size:12px;")

    def _clear_page(self):
        while self._holder_lay.count():
            w = self._holder_lay.takeAt(0).widget()
            if w:
                w.hide()          # deleteLater only runs once control returns to the event loop
                w.deleteLater()
        self._thumbs = []
        self._shots = []

    def _message(self, text):
        msg = QLabel(text)
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setWordWrap(True)
        msg.setStyleSheet("color:#8e8e93; font-size:14px;")
        self._holder_lay.addWidget(msg)

    def _rebuild_page(self):
        self._clear_page()
        if not self._entries:
            self._message("No listings yet.\n\nClick + to add an app repo (a folder with fastlane/ or a plan JSON),\n"
                          "or “Scan folder for repos…” to add all of them at once.")
            self._set_status("")
            return
        if not self._entry:
            return
        if not self._entry.exists():
            self._message(f"{self._entry.path}\nno longer exists. Remove it with ✕, or move it back.")
            self._set_status("")
            return
        if not self._source:
            self._message(f"Can't open {self._entry.name}: {self._source_error}" if self._source_error else
                          f"Nothing to preview in {self._entry.name}.\n"
                          "Expected fastlane/metadata/… screenshots or a plan JSON.")
            self._set_status("")
            return

        device = self._device_combo.currentText()
        store = "Google Play" if self._platform == "android" else "App Store"
        if not device:
            if isinstance(self._source, PlanSource):
                hint = ("Add a device with an Android frame, e.g. \"Pixel 8\"." if self._platform == "android"
                        else "Add a device with frame \"iPhone 16 Pro Max\" or \"iPad Pro 13\".")
            else:
                hint = (f"Expected images in fastlane/metadata/android/{self._source.locale}/images/phoneScreenshots/"
                        if self._platform == "android" else
                        f"Expected images in fastlane/screenshots/{self._source.locale}/")
            self._message(f"No {store} screenshots in {self._source.label}.\n{hint}")
            self._set_status(f"{self._entry.name}  ·  no {store} screenshots")
            return

        self._shots = self._source.shots(self._platform, device)
        page = self._build_store_page(device)
        self._holder_lay.addStretch()
        self._holder_lay.addWidget(page, 0, Qt.AlignmentFlag.AlignTop)
        self._holder_lay.addStretch()

        missing = self._source.missing(self._platform, device)
        status = f"{self._entry.name}  ·  {device}  ·  {len(self._shots)} screenshots"
        if self._source.locale:
            status += f"  ·  {self._source.locale}"
        status += "  ·  ● live"
        if missing:
            status += f"  ·  {len(missing)} raw screenshot(s) not found"
        self._set_status(status, error=bool(missing), tooltip="\n".join(missing))
        self._render(device)

    def _build_store_page(self, device):
        ios = self._platform == "ios"
        t = _THEMES[(self._platform, self._dark_cb.isChecked())]
        app = self._source.app_info(self._platform)
        name = app["name"]

        page = QFrame()
        page.setObjectName("storePage")
        page.setFixedWidth(_PAGE_W)
        page.setStyleSheet(f"""
            QFrame#storePage {{ background:{t['bg']}; border-radius:24px; }}
            QFrame#storePage QWidget {{ background:transparent; }}
            QFrame#storePage QLabel {{ color:{t['text']}; background:transparent; }}
            QFrame#storePage QLabel#sub {{ color:{t['sub']}; font-size:12px; }}
            QFrame#storePage QLabel#accent {{ color:{t['accent']}; font-size:14px; font-weight:600; }}
            QFrame#storePage QLabel#heading {{ font-size:18px; font-weight:600; }}
            QFrame#divider {{ background:{t['divider']}; }}
            QScrollBar:horizontal {{ height:0px; }}
        """)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 22, 0, 26)   # right edge open so the carousel bleeds off
        lay.setSpacing(14)

        def padded(widget_or_layout):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 20, 0)
            if isinstance(widget_or_layout, QWidget):
                row.addWidget(widget_or_layout)
            else:
                row.addLayout(widget_or_layout)
            lay.addLayout(row)

        # Header: icon + name + developer
        icon_size = 96 if ios else 64
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(icon_size, icon_size)
        icon_lbl.setPixmap(_app_icon(app.get("icon"), name, icon_size))

        info = QVBoxLayout()
        info.setSpacing(2)
        title = QLabel(name)
        title.setWordWrap(True)
        title.setStyleSheet(f"font-size:{22 if ios else 24}px; font-weight:{700 if ios else 500};")
        info.addWidget(title)
        if ios:
            sub = QLabel(app.get("short_description", "") or app.get("developer", ""))
            sub.setObjectName("sub")
            sub.setStyleSheet("font-size:14px;")
            sub.setWordWrap(True)
            info.addWidget(sub)
            info.addStretch()
            get_row = QHBoxLayout()
            get_btn = QLabel("Get")
            get_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            get_btn.setFixedSize(76, 30)
            get_btn.setStyleSheet(f"background:{t['accent']}; color:{t['btn_text']}; border-radius:15px;"
                                  "font-size:15px; font-weight:700;")
            get_row.addWidget(get_btn)
            get_row.addStretch()
            info.addLayout(get_row)
        else:
            dev = QLabel(app.get("developer", "Developer"))
            dev.setObjectName("accent")
            info.addWidget(dev)
            info.addStretch()

        header = QHBoxLayout()
        header.setSpacing(16)
        header.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignTop)
        header.addLayout(info, 1)
        padded(header)

        # Stats row
        rating = app.get("rating", 4.8)
        stats = QHBoxLayout()
        stats.setSpacing(0)
        if ios:
            cells = [(f"{rating}", "★★★★★"), (app.get("age", "4+"), "Age"),
                     (app.get("category", "#1"), "Chart"), (app.get("developer", "Dev")[:12], "Developer")]
        else:
            cells = [(f"{rating} ★", app.get("reviews", "1K reviews")),
                     (app.get("downloads", "10K+"), "Downloads"), (app.get("age", "Everyone"), "Rated")]
        for i, (top, bottom) in enumerate(cells):
            col = QVBoxLayout()
            col.setSpacing(1)
            a = QLabel(top)
            a.setAlignment(Qt.AlignmentFlag.AlignCenter)
            a.setStyleSheet(f"font-size:16px; font-weight:700; color:{t['sub']};" if ios
                            else "font-size:14px; font-weight:600;")
            b = QLabel(bottom)
            b.setObjectName("sub")
            b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(a)
            col.addWidget(b)
            stats.addLayout(col, 1)
            if i < len(cells) - 1:
                sep = QFrame()
                sep.setObjectName("divider")
                sep.setFixedWidth(1)
                stats.addWidget(sep)
        padded(stats)

        if not ios:
            install = QLabel("Install")
            install.setAlignment(Qt.AlignmentFlag.AlignCenter)
            install.setFixedHeight(40)
            install.setStyleSheet(f"background:{t['accent']}; color:{t['btn_text']}; border-radius:20px;"
                                  "font-size:14px; font-weight:600;")
            padded(install)

        # Screenshot carousel — sized like the store apps show them
        aspect = aspect_of(self._shots)
        thumb_h = (420 if aspect < 0.6 else 300) if ios else (232 if aspect < 0.6 else 200)
        thumb_w = int(thumb_h * aspect)
        self._thumb_radius = 18 if ios else 10

        strip = QWidget()
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(0, 0, 20, 0)
        sl.setSpacing(10 if ios else 8)
        for i in range(len(self._shots)):
            th = _Thumb(i, thumb_w, thumb_h)
            th.setStyleSheet(f"background:{t['divider']}; border-radius:{self._thumb_radius}px; color:{t['sub']};")
            th.clicked.connect(self._open_full)
            sl.addWidget(th)
            self._thumbs.append(th)
        sl.addStretch()
        carousel = QScrollArea()
        carousel.setWidget(strip)
        carousel.setWidgetResizable(True)
        carousel.setFixedHeight(thumb_h + 4)
        carousel.setFrameShape(QFrame.Shape.NoFrame)
        carousel.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        carousel.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(carousel)

        # About / description
        heading = QLabel("Description" if ios else "About this app")
        heading.setObjectName("heading")
        padded(heading)
        desc_file = "fastlane/metadata/ios/<locale>/description.txt" if ios else \
            "fastlane/metadata/android/<locale>/full_description.txt"
        desc = QLabel(app.get("description") or app.get("short_description")
                      or f"No description yet — add {desc_file}, or \"app\": {{\"description\": …}} in the plan.")
        desc.setWordWrap(True)
        desc.setObjectName("sub")
        desc.setStyleSheet("font-size:14px;")
        desc.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        padded(desc)
        return page

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render(self, device):
        if self._worker:
            self._worker.stop()
            self._stale_workers.append(self._worker)
            self._worker.finished.connect(self._reap_workers)
            self._worker = None
        self._generation += 1
        jobs = []
        for i, (_title, path, kwargs) in enumerate(self._shots):
            key = (self._platform, device, i)
            if key in self._cache:
                self._show_thumb(i, self._cache[key])
            else:
                jobs.append((key, path, kwargs))
        if not jobs:
            return
        self._worker = _RenderWorker(self._generation, jobs)
        self._worker.done.connect(self._on_rendered)
        self._worker.start()

    def _reap_workers(self):
        self._stale_workers = [w for w in self._stale_workers if w.isRunning()]

    def _on_rendered(self, generation, key, img):
        if img is not None:
            self._cache[key] = img
        if generation != self._generation:
            return
        self._show_thumb(key[2], img)

    def _show_thumb(self, idx, img):
        if idx >= len(self._thumbs):
            return
        th = self._thumbs[idx]
        if img is None:
            th.setText("✕")
            return
        th.setText("")
        th.setPixmap(_rounded_pixmap(img, th.width(), th.height(), self._thumb_radius))

    def _open_full(self, idx):
        device = self._device_combo.currentText()
        items = [(title, device, self._cache.get((self._platform, device, i)))
                 for i, (title, _p, _k) in enumerate(self._shots)]
        _FullViewDialog(self, items, idx).exec()
