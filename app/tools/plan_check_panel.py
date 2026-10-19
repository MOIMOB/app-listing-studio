"""
Plan Check — the main tool.

Left: every plan JSON found under the scan folder (default: the folder this app is
cloned in, e.g. ~/Repos), grouped by repo, each with its error/warning count.

Right: the selected plan rendered for every device, with a wireframe in place of the
screenshot, plus the checks from app/checks.py under each device. Toggle stores,
devices, locale, frames that aren't in the plan, layout guides, and real captures.
The plan file is watched: save in your editor and everything re-renders.
"""

import io
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QListWidget,
    QListWidgetItem, QScrollArea, QFrame, QFileDialog, QCheckBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, QTimer, QFileSystemWatcher, QSize, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap, QCursor, QDesktopServices

from PIL import Image, ImageDraw

from app import theme
from app.config import AppConfig
from app.checks import ERROR, WARN, check_plan, layout
from app.listing import find_plans
from app.plan import load_plan, compose_kwargs
from app.tools.config_viewer_panel import _FullViewDialog
from main import DEVICE_FRAMES, compose_image

_RENDER_W = 540
_THUMB_H = 300
_STORES = (("android", "Google Play"), ("ios", "App Store"))
_LEVEL_COLOR = {ERROR: theme.ERROR, WARN: theme.WARN}


# ─── Helpers ──────────────────────────────────────────────────────────────────

_placeholder_cache = {}


def _placeholder_screen(tablet=False) -> bytes:
    """A neutral wireframe app screen, PNG bytes."""
    key = tablet
    if key in _placeholder_cache:
        return _placeholder_cache[key]
    w, h = (1600, 2400) if tablet else (1080, 2400)
    img = Image.new("RGB", (w, h), (242, 242, 244))
    d = ImageDraw.Draw(img)
    pad = int(w * 0.06)
    d.rectangle([0, 0, w, int(h * 0.11)], fill=(228, 228, 232))
    d.rounded_rectangle([pad, int(h * 0.055), pad + int(w * 0.45), int(h * 0.075)], 12, fill=(196, 196, 202))
    y = int(h * 0.14)
    cols = 2 if tablet else 1
    cw = (w - pad * (cols + 1)) // cols
    for row in range(6):
        for c in range(cols):
            x = pad + c * (cw + pad)
            ch = int(h * (0.16 if row == 0 else 0.11))
            d.rounded_rectangle([x, y, x + cw, y + ch], 28, fill=(255, 255, 255))
            d.rounded_rectangle([x + 40, y + 40, x + 40 + int(cw * 0.5), y + 70], 10, fill=(214, 214, 220))
            d.rounded_rectangle([x + 40, y + 100, x + 40 + int(cw * 0.75), y + 124], 10, fill=(230, 230, 234))
        y += ch + int(h * 0.02)
    d.rectangle([0, int(h * 0.93), w, h], fill=(232, 232, 236))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    _placeholder_cache[key] = buf.getvalue()
    return _placeholder_cache[key]


def _pixmap(img: Image.Image, h: int) -> QPixmap:
    w = round(img.width * h / img.height)
    buf = io.BytesIO()
    img.resize((w, h), Image.LANCZOS).save(buf, format="PNG")
    px = QPixmap()
    px.loadFromData(buf.getvalue())
    return px


def _is_tablet(frame_name):
    f = DEVICE_FRAMES.get(frame_name, {})
    return bool(f.get("tablet")) or "Tablet" in frame_name or "iPad" in frame_name


def _what_if_canvas(frame_name):
    f = DEVICE_FRAMES[frame_name]
    if f.get("canvas"):
        return f["canvas"]
    if frame_name == "7 Inch Tablet":
        return (1200, 1920)
    return (1600, 2560) if _is_tablet(frame_name) else (1080, 1920)


def _ranges(idxs):
    """[0,1,2,4] → "1–3, 5" (1-based)."""
    idxs = sorted(set(idxs))
    out, start = [], None
    for i, v in enumerate(idxs):
        if start is None:
            start = v
        if i + 1 == len(idxs) or idxs[i + 1] != v + 1:
            out.append(f"{start + 1}" if start == v else f"{start + 1}–{v + 1}")
            start = None
    return ", ".join(out)


def _count_text(issues):
    e = sum(1 for i in issues if i.level == ERROR)
    w = sum(1 for i in issues if i.level == WARN)
    if not e and not w:
        return "No issues", theme.OK
    bits = []
    if e:
        bits.append(f"{e} error" + ("s" if e > 1 else ""))
    if w:
        bits.append(f"{w} warning" + ("s" if w > 1 else ""))
    return " · ".join(bits), theme.ERROR if e else theme.WARN


# ─── Render worker ────────────────────────────────────────────────────────────

class _RenderWorker(QThread):
    done = pyqtSignal(int, object, object)   # generation, key, PIL image | None

    def __init__(self, generation, jobs, guides):
        super().__init__()
        self._gen = generation
        self._jobs = jobs   # [(key, full-size kwargs)]
        self._guides = guides
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for key, kw in self._jobs:
            if self._stop:
                return
            try:
                img = self._render(kw)
            except Exception:
                img = None
            self.done.emit(self._gen, key, img)

    def _render(self, kw):
        s = _RENDER_W / kw["canvas_w"]
        small = {**kw, "canvas_w": _RENDER_W, "canvas_h": round(kw["canvas_h"] * s),
                 "phone_offset_y": int(kw["phone_offset_y"] * s)}
        img = compose_image(**small)
        if self._guides:
            self._draw_guides(img, kw, s)
        return img

    @staticmethod
    def _draw_guides(img, kw, s):
        g = layout(kw)
        d = ImageDraw.Draw(img, "RGBA")
        W = img.width
        fx, fy, fw, fh = g["frame"]
        for blk in (g["title"], g["sub"]):
            x0 = (W - blk["max_w"] * s) / 2
            d.rectangle([x0, blk["top"] * s, x0 + blk["max_w"] * s, blk["bottom"] * s],
                        outline=(94, 156, 255, 220), width=1)
        text_bottom = g["sub"]["bottom"] if kw["subtitle_text"].strip() else g["title"]["bottom"]
        bad = fy < text_bottom
        color = (229, 83, 75, 255) if bad else (91, 185, 140, 230)
        d.line([0, fy * s, W, fy * s], fill=color, width=2 if bad else 1)
        d.rectangle([fx * s, fy * s, (fx + fw) * s, (fy + fh) * s], outline=(255, 255, 255, 90), width=1)


# ─── Widgets ──────────────────────────────────────────────────────────────────

class _Thumb(QFrame):
    clicked = pyqtSignal(str, int)

    def __init__(self, device, idx, caption, w, issues):
        super().__init__()
        self._device, self._idx = device, idx
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.img = QLabel()
        self.img.setFixedSize(w, _THUMB_H)
        self.img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img.setStyleSheet(f"background:{theme.SURFACE}; border-radius:6px; color:{theme.TEXT_3};")
        lay.addWidget(self.img)

        cap = QLabel(f"{idx + 1}  {caption}")
        cap.setFixedWidth(w)
        cap.setStyleSheet(f"color:{theme.TEXT_2}; font-size:12px;")
        cap.setToolTip(caption)
        lay.addWidget(cap)

        text, color = _count_text(issues)
        mark = QLabel(text if issues else "")
        mark.setStyleSheet(f"color:{color}; font-size:11px;")
        mark.setToolTip("\n".join(i.message for i in issues))
        lay.addWidget(mark)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._device, self._idx)


def _issue_row(level, text):
    row = QHBoxLayout()
    row.setSpacing(8)
    dot = QLabel("●")
    dot.setStyleSheet(f"color:{_LEVEL_COLOR[level]}; font-size:9px;")
    dot.setFixedWidth(10)
    dot.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
    row.addWidget(dot)
    msg = QLabel(text)
    msg.setWordWrap(True)
    msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    msg.setStyleSheet(f"color:{theme.TEXT_2}; font-size:12px;")
    row.addWidget(msg, 1)
    return row


def _grouped(issues):
    """Same message on several screenshots → one row: "Screenshots 1–5: …"."""
    groups = {}
    for i in issues:
        groups.setdefault((i.level, i.message), []).append(i.shot)
    rows = []
    for (level, msg), shots in groups.items():
        idx = [s for s in shots if s >= 0]
        prefix = ""
        if idx:
            prefix = f"Screenshot {idx[0] + 1}: " if len(idx) == 1 else f"Screenshots {_ranges(idx)}: "
        rows.append((level, prefix + msg))
    return sorted(rows, key=lambda r: r[0] != ERROR)


# ─── Panel ────────────────────────────────────────────────────────────────────

class PlanCheckPanel(QWidget):
    logged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._root = AppConfig.get_scan_root()
        self._plan_paths: list[str] = []
        self._path = ""
        self._plan = None
        self._error = ""
        self._stores = {"android", "ios"}
        self._hidden_devices: set[str] = set()
        self._devices = []          # [(name, platform, device_dict, in_plan)]
        self._issues = []
        self._kwargs = {}           # (device, idx) → full-size compose kwargs
        self._images = {}           # (device, idx) → PIL
        self._thumbs = {}           # (device, idx) → _Thumb
        self._generation = 0
        self._worker = None
        self._stale = []

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(lambda _p: self._reload_timer.start())
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(300)
        self._reload_timer.timeout.connect(self._reload)

        self._build()
        QTimer.singleShot(0, self._scan)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_list_column())

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._build_header())
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        rl.addWidget(self._scroll, 1)
        root.addWidget(right, 1)
        self._set_body(self._message("Scanning…"))

    def _build_list_column(self):
        col = QWidget()
        col.setObjectName("planColumn")
        col.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        col.setFixedWidth(280)
        col.setStyleSheet(f"QWidget#planColumn {{ background:{theme.BG}; border-right:1px solid {theme.BORDER}; }}")
        lay = QVBoxLayout(col)
        lay.setContentsMargins(12, 16, 12, 12)
        lay.setSpacing(6)

        head = QHBoxLayout()
        title = QLabel("Configs")
        title.setStyleSheet(f"color:{theme.TEXT}; font-size:14px; font-weight:600;")
        head.addWidget(title, 1)
        rescan = QPushButton("Rescan")
        rescan.setObjectName("chip")
        rescan.clicked.connect(self._scan)
        head.addWidget(rescan)
        lay.addLayout(head)

        root_row = QHBoxLayout()
        self._root_lbl = QLabel()
        self._root_lbl.setStyleSheet(f"color:{theme.TEXT_3}; font-size:12px;")
        root_row.addWidget(self._root_lbl, 1)
        change = QPushButton("Change…")
        change.setFlat(True)
        change.setStyleSheet(f"QPushButton {{ color:{theme.ACCENT}; border:none; background:transparent;"
                             f" padding:0; font-size:12px; }}")
        change.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        change.clicked.connect(self._change_root)
        root_row.addWidget(change)
        lay.addLayout(root_row)
        lay.addSpacing(6)

        self._list = QListWidget()
        self._list.setStyleSheet(f"""
            QListWidget {{ background:transparent; border:none; outline:none; }}
            QListWidget::item {{ border-radius:5px; }}
            QListWidget::item:hover {{ background:{theme.SURFACE}; }}
            QListWidget::item:selected {{ background:{theme.SURFACE_2}; }}
        """)
        self._list.currentItemChanged.connect(self._on_item)
        lay.addWidget(self._list, 1)
        return col

    def _build_header(self):
        bar = QWidget()
        bar.setObjectName("checkHeader")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setStyleSheet(f"QWidget#checkHeader {{ border-bottom:1px solid {theme.BORDER}; }}")
        lay = QVBoxLayout(bar)
        lay.setContentsMargins(24, 16, 24, 14)
        lay.setSpacing(10)

        top = QHBoxLayout()
        names = QVBoxLayout()
        names.setSpacing(2)
        self._title = QLabel("")
        self._title.setStyleSheet(f"color:{theme.TEXT}; font-size:18px; font-weight:600;")
        names.addWidget(self._title)
        self._subtitle = QLabel("")
        self._subtitle.setStyleSheet(f"color:{theme.TEXT_3}; font-size:12px;")
        self._subtitle.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        names.addWidget(self._subtitle)
        top.addLayout(names, 1)
        self._summary = QLabel("")
        self._summary.setStyleSheet("font-size:13px;")
        top.addWidget(self._summary)
        self._open_btn = QPushButton("Open in editor")
        self._open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self._path)))
        top.addWidget(self._open_btn)
        lay.addLayout(top)

        controls = QHBoxLayout()
        controls.setSpacing(6)
        self._store_btns = {}
        for key, label in _STORES:
            b = QPushButton(label)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(True)
            b.toggled.connect(lambda on, k=key: self._toggle_store(k, on))
            self._store_btns[key] = b
            controls.addWidget(b)
        controls.addSpacing(10)
        self._locale_combo = QComboBox()
        self._locale_combo.setToolTip("Locale")
        self._locale_combo.currentTextChanged.connect(self._set_locale)
        controls.addWidget(self._locale_combo)
        controls.addSpacing(10)
        self._others_cb = QCheckBox("Frames not in plan")
        self._others_cb.setToolTip("Also try the plan's style on every other device frame")
        self._others_cb.toggled.connect(lambda _on: self._refresh())
        controls.addWidget(self._others_cb)
        self._guides_cb = QCheckBox("Guides")
        self._guides_cb.setToolTip("Outline the text areas and the top of the device (red when they overlap)")
        self._guides_cb.toggled.connect(lambda _on: self._rerender())
        controls.addWidget(self._guides_cb)
        self._captures_cb = QCheckBox("Use captures")
        self._captures_cb.setToolTip("Use the raw screenshots where they exist instead of the wireframe")
        self._captures_cb.toggled.connect(lambda _on: self._refresh())
        controls.addWidget(self._captures_cb)
        controls.addStretch()
        lay.addLayout(controls)

        self._device_row = QHBoxLayout()
        self._device_row.setSpacing(6)
        lay.addLayout(self._device_row)
        self._other_row = QHBoxLayout()
        self._other_row.setSpacing(6)
        lay.addLayout(self._other_row)

        self._header = bar
        bar.setVisible(False)
        return bar

    def _message(self, text):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{theme.TEXT_3}; font-size:13px;")
        return lbl

    def _set_body(self, widget):
        old = self._scroll.takeWidget()
        if old:
            old.deleteLater()
        self._scroll.setWidget(widget)

    # ── Discovery ─────────────────────────────────────────────────────────────

    def _change_root(self):
        d = QFileDialog.getExistingDirectory(self, "Folder To Scan For Plans", self._root)
        if d:
            self._root = d
            AppConfig.set_scan_root(d)
            self._scan()

    def _scan(self):
        home = os.path.expanduser("~")
        self._root_lbl.setText(self._root.replace(home, "~", 1) if self._root.startswith(home) else self._root)
        self._plan_paths = find_plans(self._root, max_depth=6) if os.path.isdir(self._root) else []
        self._list.blockSignals(True)
        self._list.clear()
        by_repo = {}
        for p in self._plan_paths:
            rel = os.path.relpath(p, self._root)
            repo = rel.split(os.sep)[0] if os.sep in rel else ""
            by_repo.setdefault(repo, []).append(p)
        select = AppConfig.get_last_checked()
        select_item = first_item = None
        for repo, paths in by_repo.items():
            if repo:
                head = QListWidgetItem()
                head.setFlags(Qt.ItemFlag.NoItemFlags)
                head.setSizeHint(QSize(0, 30))
                self._list.addItem(head)
                self._list.setItemWidget(head, self._repo_label(repo))
            for p in paths:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, p)
                item.setSizeHint(QSize(0, 44))
                self._list.addItem(item)
                rel = os.path.relpath(p, os.path.join(self._root, repo))
                self._list.setItemWidget(item, self._plan_row(rel, self._summarize(p)))
                first_item = first_item or item
                if p == select:
                    select_item = item
        self._list.blockSignals(False)
        self.logged.emit(f"Plan Check: {len(self._plan_paths)} plan(s) under {self._root}")
        select_item = select_item or first_item
        if select_item:
            self._list.setCurrentItem(select_item)
        else:
            self._header.setVisible(False)
            self._set_body(self._message(
                f"No plan JSONs under {self._root}.\n\n"
                "A plan is a JSON file with a \"screenshots\" list plus \"devices\" or \"defaults\" "
                "(see example_plan.json). Use Change… to scan another folder."))

    def _repo_label(self, repo):
        lbl = QLabel(repo)
        lbl.setStyleSheet(f"color:{theme.TEXT_3}; font-size:12px; font-weight:600; padding:8px 8px 0 8px;")
        return lbl

    def _plan_row(self, rel, status):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 4, 8, 4)
        lay.setSpacing(1)
        name = QLabel(rel)
        name.setStyleSheet(f"color:{theme.TEXT}; font-size:13px;")
        lay.addWidget(name)
        text, color = status
        st = QLabel(text)
        st.setObjectName("status")
        st.setStyleSheet(f"color:{color}; font-size:11px;")
        lay.addWidget(st)
        return w

    def _summarize(self, path):
        try:
            plan = load_plan(path)
            return _count_text(check_plan(plan, self._plan_devices(plan)))
        except Exception as e:
            return f"Can't read: {e}"[:60], theme.ERROR

    def _update_list_status(self):
        item = self._list.currentItem()
        w = self._list.itemWidget(item) if item else None
        if not w:
            return
        st = w.findChild(QLabel, "status")
        text, color = (f"Can't read: {self._error}"[:60], theme.ERROR) if self._error else _count_text(self._issues)
        st.setText(text)
        st.setStyleSheet(f"color:{color}; font-size:11px;")

    # ── Plan ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _plan_devices(plan):
        return [(plan.device_name(i), plan.platform(d), d, True) for i, d in enumerate(plan.devices)]

    def _what_if_devices(self, plan):
        used = {plan.cfg(d, {}).get("frame") for d in plan.devices}
        out = []
        for frame_name, frame in DEVICE_FRAMES.items():
            if frame_name in used:
                continue
            platform = frame.get("platform", "android")
            tablet = _is_tablet(frame_name)
            # Borrow sizing from the closest plan device: same store and phone/tablet
            base = next((d for d in plan.devices if plan.platform(d) == platform
                         and _is_tablet(plan.cfg(d, {}).get("frame", "")) == tablet), {})
            w, h = _what_if_canvas(frame_name)
            device = {**base, "name": frame_name, "frame": frame_name, "canvas_w": w, "canvas_h": h,
                      "platform": platform}
            out.append((frame_name, platform, device, False))
        return out

    def _on_item(self, item, _prev=None):
        path = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not path:
            return
        self._path = path
        AppConfig.set_last_checked(path)
        self._hidden_devices = set()
        self._load(locale="")
        self._watch()

    def _watch(self):
        old = self._watcher.files()
        if old:
            self._watcher.removePaths(old)
        if self._path and os.path.exists(self._path):
            self._watcher.addPath(self._path)

    def _reload(self):
        self._load(locale=self._plan.locale if self._plan else "")
        self._watch()   # editors that save atomically replace the file
        self.logged.emit(f"Plan Check: reloaded {os.path.basename(self._path)}")

    def _load(self, locale):
        try:
            self._plan = load_plan(self._path, locale)
            self._error = ""
        except Exception as e:
            self._error = str(e)
        home = os.path.expanduser("~")
        rel = os.path.relpath(self._path, self._root)
        self._title.setText(rel.split(os.sep)[0] if os.sep in rel else os.path.basename(self._path))
        self._subtitle.setText(self._path.replace(home, "~", 1))
        self._header.setVisible(True)

        self._locale_combo.blockSignals(True)
        self._locale_combo.clear()
        if self._plan:
            self._locale_combo.addItems(list(self._plan.locales))
            self._locale_combo.setCurrentText(self._plan.locale)
        self._locale_combo.setVisible(bool(self._plan and len(self._plan.locales) > 1))
        self._locale_combo.blockSignals(False)
        self._refresh()

    def _set_locale(self, locale):
        if self._plan and locale and locale != self._plan.locale:
            self._load(locale)

    def _toggle_store(self, key, on):
        (self._stores.add if on else self._stores.discard)(key)
        self._refresh()

    def _toggle_device(self, name, on):
        (self._hidden_devices.discard if on else self._hidden_devices.add)(name)
        self._refresh(rebuild_chips=False)

    # ── Build page ────────────────────────────────────────────────────────────

    def _refresh(self, rebuild_chips=True):
        if self._error and not self._plan:
            self._summary.setText("")
            self._set_body(self._message(f"Can't read {os.path.basename(self._path)}:\n{self._error}"))
            self._update_list_status()
            return
        if self._error:
            self._summary.setText("Invalid JSON — showing the last good version")
            self._summary.setStyleSheet(f"color:{theme.ERROR}; font-size:13px;")
            self._summary.setToolTip(self._error)
            return

        plan = self._plan
        all_devices = self._plan_devices(plan)
        if self._others_cb.isChecked():
            all_devices += self._what_if_devices(plan)
        in_store = [d for d in all_devices if d[1] in self._stores]
        if rebuild_chips:
            self._build_device_chips(in_store)
        self._devices = [d for d in in_store if d[0] not in self._hidden_devices]

        self._issues = check_plan(plan, self._devices)
        text, color = _count_text(self._issues)
        n_images = len(self._devices) * len(plan.screenshots)
        self._summary.setText(f"{n_images} images  ·  {text}")
        self._summary.setStyleSheet(f"color:{color}; font-size:13px;")
        self._summary.setToolTip("")
        self._update_list_status()

        self._kwargs = {}
        shots = plan.shots()
        for name, platform, device, _in_plan in self._devices:
            tablet = _is_tablet(plan.cfg(device, {}).get("frame", ""))
            for i, shot in enumerate(shots):
                cfg = plan.cfg(device, shot)
                data, native = None, False
                if self._captures_cb.isChecked():
                    src = plan.source_path(cfg)
                    if src and os.path.exists(src):
                        with open(src, "rb") as f:
                            data = f.read()
                        native = cfg.get("ios_native", False)
                if data is None:
                    data, native = _placeholder_screen(tablet), True
                try:
                    kw = compose_kwargs(cfg, data)
                    kw["ios_native"] = native
                    self._kwargs[(name, i)] = kw
                except Exception:
                    pass
        self._build_body(shots)
        self._rerender()

    def _build_device_chips(self, devices):
        for row in (self._device_row, self._other_row):
            while row.count():
                w = row.takeAt(0).widget()
                if w:
                    w.deleteLater()
        if any(not in_plan for *_x, in_plan in devices):
            lbl = QLabel("Not in plan")
            lbl.setStyleSheet(f"color:{theme.TEXT_3}; font-size:12px; padding-right:4px;")
            self._other_row.addWidget(lbl)
        for name, _platform, _device, in_plan in devices:
            b = QPushButton(name)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setChecked(name not in self._hidden_devices)
            b.toggled.connect(lambda on, n=name: self._toggle_device(n, on))
            (self._device_row if in_plan else self._other_row).addWidget(b)
        self._device_row.addStretch()
        self._other_row.addStretch()

    def _build_body(self, shots):
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(24, 20, 24, 28)
        lay.setSpacing(28)
        self._thumbs = {}

        plan_issues = [i for i in self._issues if not i.device]
        if plan_issues:
            box = QVBoxLayout()
            box.setSpacing(6)
            head = QLabel("Plan")
            head.setStyleSheet(f"color:{theme.TEXT}; font-size:14px; font-weight:600;")
            box.addWidget(head)
            for level, text in _grouped(plan_issues):
                box.addLayout(_issue_row(level, text))
            lay.addLayout(box)

        plan_stores = {platform for _n, platform, _d, in_plan in self._devices if in_plan}
        for key, label in _STORES:
            if key in self._stores and key not in plan_stores and not self._others_cb.isChecked():
                note = QLabel(f"This plan has no {label} devices. Tick “Frames not in plan” to see how its "
                              f"style works on {label} frames.")
                note.setWordWrap(True)
                note.setStyleSheet(f"color:{theme.TEXT_3}; font-size:12px;")
                lay.addWidget(note)
        if not self._devices:
            lay.addWidget(self._message("No devices for the selected stores."))
        for name, platform, device, in_plan in self._devices:
            lay.addWidget(self._device_section(name, platform, device, in_plan, shots))
        lay.addStretch()
        self._set_body(body)

    def _device_section(self, name, platform, device, in_plan, shots):
        sec = QWidget()
        sl = QVBoxLayout(sec)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(10)

        issues = [i for i in self._issues if i.device == name]
        kw0 = self._kwargs.get((name, 0))
        head = QHBoxLayout()
        title = QLabel(name)
        title.setStyleSheet(f"color:{theme.TEXT}; font-size:14px; font-weight:600;")
        head.addWidget(title)
        store = dict(_STORES)[platform]
        meta = [store]
        if kw0:
            meta += [kw0["frame_name"], f"{kw0['canvas_w']}×{kw0['canvas_h']}"]
        if not in_plan:
            meta.append("not in plan — sized like the closest plan device")
        m = QLabel("  ·  ".join(meta))
        m.setStyleSheet(f"color:{theme.TEXT_3}; font-size:12px;")
        head.addWidget(m)
        head.addStretch()
        text, color = _count_text(issues)
        st = QLabel(text)
        st.setStyleSheet(f"color:{color}; font-size:12px;")
        head.addWidget(st)
        sl.addLayout(head)

        strip = QWidget()
        row = QHBoxLayout(strip)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        for i, shot in enumerate(shots):
            kw = self._kwargs.get((name, i))
            aspect = kw["canvas_w"] / kw["canvas_h"] if kw else 9 / 16
            caption = (kw["title_text"].strip() if kw else "") or shot.get("filename", "")
            th = _Thumb(name, i, caption, round(_THUMB_H * aspect),
                        [x for x in issues if x.shot == i])
            th.clicked.connect(self._open_full)
            row.addWidget(th)
            self._thumbs[(name, i)] = th
        row.addStretch()
        carousel = QScrollArea()
        carousel.setWidget(strip)
        carousel.setWidgetResizable(True)
        carousel.setFrameShape(QFrame.Shape.NoFrame)
        carousel.setFixedHeight(_THUMB_H + 66)
        carousel.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sl.addWidget(carousel)

        for level, text in _grouped(issues):
            sl.addLayout(_issue_row(level, text))
        sec.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        return sec

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _rerender(self):
        if self._worker:
            self._worker.stop()
            self._stale.append(self._worker)
            self._worker.finished.connect(lambda: setattr(self, "_stale", [w for w in self._stale if w.isRunning()]))
            self._worker = None
        self._generation += 1
        self._images = {}
        jobs = [(k, kw) for k, kw in self._kwargs.items()]
        for th in self._thumbs.values():
            th.img.setText("Rendering…")
        if not jobs:
            return
        self._worker = _RenderWorker(self._generation, jobs, self._guides_cb.isChecked())
        self._worker.done.connect(self._on_rendered)
        self._worker.start()

    def _on_rendered(self, generation, key, img):
        if generation != self._generation:
            return
        self._images[key] = img
        th = self._thumbs.get(key)
        if not th:
            return
        if img is None:
            th.img.setText("Render failed")
            th.img.setStyleSheet(f"background:{theme.SURFACE}; border-radius:6px; color:{theme.ERROR};")
        else:
            th.img.setText("")
            th.img.setPixmap(_pixmap(img, _THUMB_H))

    def _open_full(self, device, idx):
        n = len(self._plan.screenshots)
        items = []
        for i in range(n):
            kw = self._kwargs.get((device, i))
            items.append(((kw["title_text"].strip() if kw else "") or f"#{i + 1}", device, self._images.get((device, i))))
        _FullViewDialog(self, items, idx).exec()
