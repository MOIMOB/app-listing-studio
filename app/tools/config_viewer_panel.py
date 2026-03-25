"""
Config Viewer — loads a JSON plan file and shows rendered store listing
previews for all screenshots × devices in a read-only card grid.

Card click (or Enter) → full-view dialog with left/right arrow navigation.
"""

import sys
import os
import json
import io

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QFileDialog, QDialog, QSizePolicy,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QKeyEvent, QCursor

from PIL import Image

# ── import shared helpers from root main.py ──────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from main import compose_image, PRESETS, DEVICE_FRAMES  # noqa: E402

# Render resolution for the viewer (scaled down from full canvas for speed)
_RENDER_W = 540   # full-view PIL image width
_THUMB_W = 180    # card thumbnail width
_THUMB_H = 320    # card thumbnail height  (9:16 ≈ same ratio as 1440×2560)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _cfg_to_kwargs(cfg: dict, screenshot_bytes) -> dict:
    preset = cfg.get("preset")
    if preset and preset in PRESETS and PRESETS[preset]:
        bg1, bg2 = PRESETS[preset]
    else:
        bg1 = cfg.get("bg_color1", "#1a0533")
        bg2 = cfg.get("bg_color2", "#3d1065")

    frame = cfg.get("frame", list(DEVICE_FRAMES)[0])
    if frame not in DEVICE_FRAMES:
        frame = list(DEVICE_FRAMES)[0]

    canvas_w = cfg.get("canvas_w", 1440)
    canvas_h = cfg.get("canvas_h", 2560)
    # Scale down to _RENDER_W for speed
    scale = _RENDER_W / canvas_w
    render_w = _RENDER_W
    render_h = int(canvas_h * scale)

    return dict(
        screenshot_bytes=screenshot_bytes,
        frame_name=frame,
        bg_color1=bg1,
        bg_color2=bg2,
        title_text=cfg.get("title", ""),
        subtitle_text=cfg.get("subtitle", ""),
        title_color=cfg.get("title_color", "#ffffff"),
        subtitle_color=cfg.get("subtitle_color", "#cccccc"),
        title_size=cfg.get("title_size", 72),
        subtitle_size=cfg.get("subtitle_size", 38),
        shadow_enabled=cfg.get("shadow", True),
        phone_scale=cfg.get("phone_size", 150) / 100,
        phone_offset_y=int(cfg.get("phone_offset_y", 0) * scale),
        canvas_w=render_w,
        canvas_h=render_h,
    )


def _pil_to_pixmap(img: Image.Image, w: int, h: int) -> QPixmap:
    thumb = img.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, format="PNG")
    px = QPixmap()
    px.loadFromData(buf.getvalue())
    return px


# ─── Background render worker ─────────────────────────────────────────────────

class _RenderWorker(QThread):
    # dev_idx, shot_idx, QPixmap thumbnail (or None), PIL Image (or None)
    done = pyqtSignal(int, int, object, object)

    def __init__(self, dev_idx: int, shot_idx: int, kwargs: dict):
        super().__init__()
        self._dev_idx = dev_idx
        self._shot_idx = shot_idx
        self._kwargs = kwargs

    def run(self):
        try:
            img = compose_image(**self._kwargs)
            px = _pil_to_pixmap(img, _THUMB_W, _THUMB_H)
            self.done.emit(self._dev_idx, self._shot_idx, px, img)
        except Exception:
            self.done.emit(self._dev_idx, self._shot_idx, None, None)


# ─── Card widget ──────────────────────────────────────────────────────────────

class _CardWidget(QFrame):
    clicked = pyqtSignal(int)  # flat_idx

    def __init__(self, flat_idx: int, title: str, shot_num: int):
        super().__init__()
        self._flat_idx = flat_idx
        self.setFixedSize(_THUMB_W + 18, _THUMB_H + 58)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet("""
            QFrame {
                background: #16162a;
                border: 1px solid #2a2a4a;
                border-radius: 10px;
            }
            QFrame:hover { border-color: #7c3aed; background: #1c1c38; }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(9, 9, 9, 9)
        lay.setSpacing(6)

        self._img_lbl = QLabel("⏳")
        self._img_lbl.setFixedSize(_THUMB_W, _THUMB_H)
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet(
            "background:#0a0a18; border-radius:6px; border:none; color:#555; font-size:22px;"
        )
        lay.addWidget(self._img_lbl)

        short = (title[:20] + "…") if len(title) > 20 else title
        lbl = QLabel(f"#{shot_num}  {short}")
        lbl.setStyleSheet(
            "color:#ccd; font-size:11px; font-weight:bold; border:none; background:transparent;"
        )
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

    def set_pixmap(self, px: QPixmap):
        self._img_lbl.setText("")
        self._img_lbl.setPixmap(px)

    def set_error(self):
        self._img_lbl.setText("✕")
        self._img_lbl.setStyleSheet(
            "background:#1a0a0a; border-radius:6px; border:none; color:#a33; font-size:22px;"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._flat_idx)


# ─── Full-view dialog ─────────────────────────────────────────────────────────

class _FullViewDialog(QDialog):
    def __init__(self, parent, items: list, start_idx: int):
        """
        items: list of (title, device_name, pil_img | None)
        Passed by reference — updates from background renders are visible.
        """
        super().__init__(parent)
        self.setWindowTitle("Config Viewer — Full View")
        self.setModal(True)
        self.resize(660, 860)
        self.setStyleSheet("QDialog { background: #0a0a18; } QLabel { color: #dde; }")

        self._items = items
        self._idx = start_idx

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 16)
        lay.setSpacing(8)

        # ── Nav bar ──
        nav = QHBoxLayout()
        nav.setSpacing(8)

        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedWidth(44)
        self._prev_btn.clicked.connect(self._prev)
        nav.addWidget(self._prev_btn)

        self._info = QLabel()
        self._info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info.setStyleSheet("color:#99a; font-size:12px;")
        nav.addWidget(self._info, 1)

        self._next_btn = QPushButton("▶")
        self._next_btn.setFixedWidth(44)
        self._next_btn.clicked.connect(self._next)
        nav.addWidget(self._next_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedWidth(36)
        close_btn.setToolTip("Close  (Esc)")
        close_btn.clicked.connect(self.accept)
        nav.addWidget(close_btn)

        lay.addLayout(nav)

        # ── Image area ──
        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._img_lbl.setStyleSheet("background: #0d0d1e; border-radius: 10px;")
        lay.addWidget(self._img_lbl, 1)

        self._show(self._idx)

    # ── Rendering ──

    def _show(self, idx: int):
        self._idx = idx
        title, device_name, pil_img = self._items[idx]
        total = len(self._items)

        self._info.setText(f"{device_name}  ·  {idx + 1} / {total}  ·  {title}")
        self._prev_btn.setEnabled(idx > 0)
        self._next_btn.setEnabled(idx < total - 1)

        if pil_img is not None:
            avail_w = max(300, self.width() - 32)
            avail_h = max(400, self.height() - 100)
            iw, ih = pil_img.size
            scale = min(avail_w / iw, avail_h / ih)
            px = _pil_to_pixmap(pil_img, int(iw * scale), int(ih * scale))
            self._img_lbl.setPixmap(px)
            self._img_lbl.setText("")
        else:
            self._img_lbl.setPixmap(QPixmap())
            self._img_lbl.setText("Still rendering…")
            self._img_lbl.setStyleSheet(
                "background:#0d0d1e; border-radius:10px; color:#555; font-size:14px;"
            )

    def _prev(self):
        if self._idx > 0:
            self._show(self._idx - 1)

    def _next(self):
        if self._idx < len(self._items) - 1:
            self._show(self._idx + 1)

    # ── Events ──

    def keyPressEvent(self, event: QKeyEvent):
        k = event.key()
        if k in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self._prev()
        elif k in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self._next()
        elif k == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._show(self._idx)


# ─── Main panel ───────────────────────────────────────────────────────────────

class ConfigViewerPanel(QWidget):
    logged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._plan_defaults: dict = {}
        self._plan_devices: list = []
        self._plan_screenshots: list = []
        self._plan_dir: str = ""
        self._source_dir: str = ""
        # Flat ordering: device0_shot0, device0_shot1, …, device1_shot0, …
        self._cards: list[_CardWidget] = []
        self._full_items: list[tuple] = []  # (title, device_name, pil_img|None)
        self._workers: list[_RenderWorker] = []
        self._build()
        # Auto-load the example plan if it exists
        _example = os.path.join(_ROOT, "example_plan.json")
        if os.path.exists(_example):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._load_config_path(_example))

    # ── UI construction ───────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Toolbar
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet("background:#13131f; border-bottom:1px solid #2a2a4a;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 8, 16, 8)
        bl.setSpacing(10)

        load_btn = QPushButton("📂  Load Config")
        load_btn.setObjectName("primary")
        load_btn.clicked.connect(self._load_config)
        bl.addWidget(load_btn)

        self._src_btn = QPushButton("📁  Screenshot Folder")
        self._src_btn.setToolTip("Folder containing the raw screenshot .png files referenced in the config")
        self._src_btn.clicked.connect(self._browse_source)
        self._src_btn.setEnabled(False)
        bl.addWidget(self._src_btn)

        self._render_btn = QPushButton("🔄  Re-render")
        self._render_btn.clicked.connect(self._render_all)
        self._render_btn.setEnabled(False)
        bl.addWidget(self._render_btn)

        bl.addStretch()

        self._status = QLabel("Load a config file to begin")
        self._status.setStyleSheet("color:#7a7a9a; font-size:12px;")
        bl.addWidget(self._status)

        outer.addWidget(bar)

        # Scrollable content
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._content.setStyleSheet("background:#0f0f1a;")
        self._content_lay = QVBoxLayout(self._content)
        self._content_lay.setContentsMargins(20, 20, 20, 20)
        self._content_lay.setSpacing(20)
        self._content_lay.addStretch()

        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, 1)

    # ── Config loading ────────────────────────────────────────────────────────

    def _load_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Config", "", "JSON (*.json)")
        if path:
            self._load_config_path(path)

    def _load_config_path(self, path: str):
        try:
            with open(path) as f:
                raw = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))
            return

        if isinstance(raw, list):
            self._plan_defaults = {}
            self._plan_devices = [{}]
            self._plan_screenshots = raw
        else:
            self._plan_defaults = raw.get("defaults", {})
            self._plan_devices = raw.get("devices", [{}])
            self._plan_screenshots = raw.get("screenshots", [])

        self._plan_dir = os.path.dirname(path)
        self._source_dir = self._plan_dir

        n_dev = len(self._plan_devices)
        n_shots = len(self._plan_screenshots)
        self._status.setText(
            f"{os.path.basename(path)}  —  {n_dev} device(s) × {n_shots} screenshots"
        )
        self.logged.emit(f"Config Viewer: loaded {os.path.basename(path)}")

        self._src_btn.setEnabled(True)
        self._render_btn.setEnabled(True)
        self._build_grid()
        self._render_all()

    def _browse_source(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Screenshot Folder", self._source_dir
        )
        if d:
            self._source_dir = d
            self.logged.emit(f"Config Viewer: screenshot folder → {d}")
            self._render_all()

    # ── Grid ──────────────────────────────────────────────────────────────────

    def _build_grid(self):
        # Clear previous content
        while self._content_lay.count():
            item = self._content_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self._cards = []
        self._full_items = []
        flat_idx = 0

        for dev_idx, device in enumerate(self._plan_devices):
            dev_name = (
                device.get("name")
                or device.get("fastlane_dir")
                or f"Device {dev_idx + 1}"
            )
            is_tablet = "tablet" in dev_name.lower()
            icon = "📟" if is_tablet else "📱"

            # Section header
            hdr = QLabel(f"{icon}  {dev_name}")
            hdr.setStyleSheet(
                "color:#aab; font-size:13px; font-weight:bold; "
                "letter-spacing:1px; padding:4px 0 8px 0; background:transparent;"
            )
            self._content_lay.addWidget(hdr)

            # Cards row
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            row_lay = QHBoxLayout(row_w)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(12)
            row_lay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

            for shot_idx, shot in enumerate(self._plan_screenshots):
                cfg = {**self._plan_defaults, **device, **shot}
                title = cfg.get("title") or cfg.get("filename") or f"Screenshot {shot_idx + 1}"

                card = _CardWidget(flat_idx, title, shot_idx + 1)
                card.clicked.connect(self._open_fullview)
                row_lay.addWidget(card)

                self._cards.append(card)
                self._full_items.append((title, dev_name, None))
                flat_idx += 1

            row_lay.addStretch()

            # Wrap in horizontal scroll area
            row_scroll = QScrollArea()
            row_scroll.setWidget(row_w)
            row_scroll.setWidgetResizable(True)
            row_scroll.setFixedHeight(_THUMB_H + 80)
            row_scroll.setFrameShape(QFrame.Shape.NoFrame)
            row_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            row_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            row_scroll.setStyleSheet("background:transparent;")
            self._content_lay.addWidget(row_scroll)

        self._content_lay.addStretch()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render_all(self):
        if not self._plan_screenshots or not self._plan_devices:
            return

        # Cancel previous workers
        for w in self._workers:
            w.quit()
        self._workers = []

        # Reset full_items pil to None
        self._full_items = [
            (title, dev_name, None) for title, dev_name, _ in self._full_items
        ]

        total = len(self._plan_devices) * len(self._plan_screenshots)
        self._status.setText(f"Rendering {total} previews…")

        for dev_idx, device in enumerate(self._plan_devices):
            for shot_idx, shot in enumerate(self._plan_screenshots):
                cfg = {**self._plan_defaults, **device, **shot}
                screenshot_bytes = self._load_screenshot(cfg.get("filename", ""))
                kwargs = _cfg_to_kwargs(cfg, screenshot_bytes)

                w = _RenderWorker(dev_idx, shot_idx, kwargs)
                w.done.connect(self._on_render_done)
                self._workers.append(w)
                w.start()

    def _load_screenshot(self, filename: str):
        if not filename:
            return None
        path = os.path.join(self._source_dir, filename)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception:
            return None

    def _on_render_done(self, dev_idx: int, shot_idx: int, pixmap, pil_img):
        n_shots = len(self._plan_screenshots)
        flat_idx = dev_idx * n_shots + shot_idx

        if not (0 <= flat_idx < len(self._cards)):
            return

        if pixmap is not None:
            self._cards[flat_idx].set_pixmap(pixmap)
        else:
            self._cards[flat_idx].set_error()

        title, dev_name, _ = self._full_items[flat_idx]
        self._full_items[flat_idx] = (title, dev_name, pil_img)

        # Update status once all done
        rendered = sum(1 for _, _, img in self._full_items if img is not None)
        total = len(self._full_items)
        if rendered == total:
            n_dev = len(self._plan_devices)
            self._status.setText(
                f"{n_dev} device(s) × {n_shots} screenshots — all rendered ✓"
            )
            self.logged.emit(f"Config Viewer: {total} previews ready.")

    # ── Full view ─────────────────────────────────────────────────────────────

    def _open_fullview(self, flat_idx: int):
        dlg = _FullViewDialog(self, self._full_items, flat_idx)
        dlg.exec()
