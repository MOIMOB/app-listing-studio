"""
App Listing Studio — Android Store Listing Asset Generator
Desktop app using PyQt6 + ADB + Pillow (Windows & Linux)
"""

import sys
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QSlider, QFileDialog,
    QScrollArea, QFrame, QColorDialog, QMessageBox, QProgressBar,
    QSplitter, QGroupBox, QSpinBox, QCheckBox, QGridLayout, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import (
    QPixmap, QImage, QColor, QPainter, QFont, QLinearGradient,
    QBrush, QPen, QIcon, QPalette
)
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io

# ─── Constants ────────────────────────────────────────────────────────────────

CANVAS_W = 1080
CANVAS_H = 1920
APP_VERSION = "1.1.0"

DEVICE_FRAMES = {
    "Pixel 8": {
        "width": 340, "height": 700,
        "border": 18, "radius": 52,
        "color": "#1a1a1a", "highlight": "#2e2e2e",
        "punch_hole": True, "button_right": True,
    },
    "Samsung S24": {
        "width": 330, "height": 695,
        "border": 16, "radius": 50,
        "color": "#111111", "highlight": "#2a2a2a",
        "punch_hole": True, "button_right": True,
    },
    "Generic Android Phone": {
        "width": 320, "height": 670,
        "border": 14, "radius": 40,
        "color": "#222222", "highlight": "#333333",
        "punch_hole": False, "button_right": True,
    },
    "Pixel Tablet": {
        "width": 500, "height": 776,
        "border": 20, "radius": 28,
        "color": "#2a2a2a", "highlight": "#3a3a3a",
        "punch_hole": False, "button_right": True,
    },
    "Generic Tablet": {
        "width": 560, "height": 740,
        "border": 18, "radius": 30,
        "color": "#1a1a1a", "highlight": "#2a2a2a",
        "punch_hole": False, "button_right": False,
    },
    "7 Inch Tablet": {
        "width": 370, "height": 640,
        "border": 14, "radius": 22,
        "color": "#1a1a1a", "highlight": "#2a2a2a",
        "punch_hole": False, "button_right": True,
    },
    "10 Inch Tablet": {
        "width": 480, "height": 740,
        "border": 18, "radius": 26,
        "color": "#222222", "highlight": "#323232",
        "punch_hole": False, "button_right": True,
    },
}

PRESETS = {
    "Midnight Purple": ("#1a0533", "#3d1065"),
    "Ocean Blue":      ("#0d1b3e", "#1a4f8a"),
    "Forest Green":    ("#0a2e1a", "#1a5c35"),
    "Coral Sunset":    ("#8b1a1a", "#cc4a1a"),
    "Charcoal":        ("#1a1a1a", "#3a3a3a"),
    "Rose Gold":       ("#3d1a2e", "#8a3a5c"),
    "Amber":           ("#2e1a00", "#6b3d00"),
    "Custom":          None,
}

# ─── ADB Worker ───────────────────────────────────────────────────────────────

class ADBWorker(QThread):
    devices_found = pyqtSignal(list)
    screenshot_done = pyqtSignal(bytes)
    error = pyqtSignal(str)
    log = pyqtSignal(str)
    secure_flag_warning = pyqtSignal()
    avds_found = pyqtSignal(list)

    def __init__(self, action, device_id=None):
        super().__init__()
        self.action = action
        self.device_id = device_id

    def run(self):
        if self.action == "list":
            self._list_devices()
        elif self.action == "screenshot":
            self._take_screenshot()

    def _run_adb(self, args, timeout=15):
        cmd = ["adb"] + args
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr.decode(errors="replace")
        except FileNotFoundError:
            return -1, b"", "ADB not found. Please install Android Platform Tools and add to PATH."
        except subprocess.TimeoutExpired:
            return -1, b"", "ADB command timed out."

    def _list_devices(self):
        self.log.emit("Scanning for ADB devices...")
        code, out, err = self._run_adb(["devices", "-l"])
        if code != 0:
            self.error.emit(err)
            return
        lines = out.decode(errors="replace").strip().splitlines()[1:]
        devices = []
        for line in lines:
            parts = line.split()
            if len(parts) < 2 or parts[1] != "device":
                continue
            serial = parts[0]

            # ── Detect emulator vs physical ──────────────────────────────
            # Emulator serials look like "emulator-5554"
            is_emulator = serial.startswith("emulator-") or "emulator" in serial.lower()

            # Also check via ro.kernel.qemu property (returns "1" on AVD)
            if not is_emulator:
                _, qemu_out, _ = self._run_adb(["-s", serial, "shell", "getprop", "ro.kernel.qemu"])
                is_emulator = qemu_out.decode(errors="replace").strip() == "1"

            # Get model name
            _, model_out, _ = self._run_adb(["-s", serial, "shell", "getprop", "ro.product.model"])
            model = model_out.decode(errors="replace").strip() or serial

            # For emulators also get the AVD name (much friendlier)
            avd_name = None
            if is_emulator:
                _, avd_out, _ = self._run_adb(["-s", serial, "emu", "avd", "name"])
                raw = avd_out.decode(errors="replace").strip().splitlines()
                # First non-empty line is the AVD name, second is "OK"
                if raw:
                    avd_name = raw[0].strip()

            # Get Android version
            _, ver_out, _ = self._run_adb(["-s", serial, "shell", "getprop", "ro.build.version.release"])
            android_ver = ver_out.decode(errors="replace").strip()

            # Get screen resolution (useful to know)
            _, res_out, _ = self._run_adb(["-s", serial, "shell", "wm", "size"])
            resolution = res_out.decode(errors="replace").strip().replace("Physical size: ", "")

            devices.append({
                "serial": serial,
                "model": model,
                "is_emulator": is_emulator,
                "avd_name": avd_name,
                "android_ver": android_ver,
                "resolution": resolution,
            })

        emulators = sum(1 for d in devices if d["is_emulator"])
        physical = len(devices) - emulators
        self.log.emit(
            f"Found {len(devices)} device(s): {emulators} emulator(s), {physical} physical."
        )
        self.devices_found.emit(devices)

        # List available (non-running) AVDs
        try:
            result = subprocess.run(
                ["emulator", "-list-avds"], capture_output=True, timeout=10
            )
            all_avds = [l.strip() for l in result.stdout.decode(errors="replace").splitlines() if l.strip()]
            running_avd_names = {d.get("avd_name") for d in devices if d["is_emulator"]}
            available = [n for n in all_avds if n not in running_avd_names]
            self.avds_found.emit(available)
        except Exception:
            self.avds_found.emit([])

    def _take_screenshot(self):
        self.log.emit(f"Capturing screenshot from {self.device_id}...")
        args = ["-s", self.device_id, "exec-out", "screencap", "-p"]
        code, out, err = self._run_adb(args, timeout=20)
        if code != 0 or len(out) < 100:
            self.error.emit(f"Screenshot failed: {err or 'No data received'}")
            return
        # Detect all-black image (FLAG_SECURE symptom)
        try:
            img = Image.open(io.BytesIO(out)).convert("L")
            mean_brightness = sum(img.getdata()) / (img.width * img.height)
            if mean_brightness < 5:
                self.secure_flag_warning.emit()
        except Exception:
            pass
        self.log.emit("Screenshot captured!")
        self.screenshot_done.emit(out)


# ─── Emulator Start Worker ────────────────────────────────────────────────────

class EmulatorStartWorker(QThread):
    device_ready = pyqtSignal()
    log = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, avd_name):
        super().__init__()
        self.avd_name = avd_name

    def run(self):
        self.log.emit(f"Starting emulator '{self.avd_name}'...")
        try:
            subprocess.Popen(["emulator", "-avd", self.avd_name])
        except FileNotFoundError:
            self.error.emit("emulator not found in PATH. Make sure Android SDK emulator is installed.")
            return

        import time
        self.log.emit("Waiting for emulator to boot (this may take a minute)...")
        for _ in range(60):
            time.sleep(3)
            try:
                result = subprocess.run(["adb", "devices"], capture_output=True, timeout=5)
                lines = result.stdout.decode(errors="replace").strip().splitlines()[1:]
                for line in lines:
                    if "\tdevice" in line and "emulator" in line:
                        self.log.emit("Emulator ready!")
                        self.device_ready.emit()
                        return
            except Exception:
                pass
        self.error.emit("Emulator timed out after 3 minutes. Try clicking ⟳ Scan manually.")


# ─── Image Composer ───────────────────────────────────────────────────────────

def compose_image(
    screenshot_bytes,
    frame_name,
    bg_color1, bg_color2,
    title_text, subtitle_text,
    title_color, subtitle_color,
    title_size, subtitle_size,
    shadow_enabled=True,
    phone_scale=1.50,
    phone_offset_y=0,
    canvas_w=1440,
    canvas_h=2560,
):
    """Compose final store listing image."""

    img = Image.new("RGB", (canvas_w, canvas_h))
    draw = ImageDraw.Draw(img)

    # ── Background gradient ──
    c1 = _hex_to_rgb(bg_color1)
    c2 = _hex_to_rgb(bg_color2)
    for y in range(canvas_h):
        t = y / canvas_h
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        draw.line([(0, y), (canvas_w, y)], fill=(r, g, b))

    # ── Subtle noise texture ──
    import random
    rng = random.Random(42)
    for _ in range(8000):
        x = rng.randint(0, canvas_w - 1)
        y = rng.randint(0, canvas_h - 1)
        v = rng.randint(0, 30)
        px = img.getpixel((x, y))
        img.putpixel((x, y), tuple(min(255, p + v) for p in px))

    draw = ImageDraw.Draw(img)

    # ── Text area: top 38% ──
    text_area_h = int(canvas_h * 0.38)

    # Scale font sizes proportionally to canvas vs baseline 1440×2560
    scale_f = canvas_w / 1440
    title_font = _load_font(int(title_size * scale_f), bold=True)
    subtitle_font = _load_font(int(subtitle_size * scale_f), bold=False)

    # Draw title
    title_y = int(text_area_h * 0.28)
    _draw_text_centered(
        draw, img, title_text, canvas_w // 2, title_y,
        title_font, _hex_to_rgb(title_color),
        shadow=shadow_enabled, max_width=canvas_w - int(120 * scale_f)
    )

    # Draw subtitle
    subtitle_y = title_y + int(title_size * scale_f) + int(28 * scale_f)
    _draw_text_centered(
        draw, img, subtitle_text, canvas_w // 2, subtitle_y,
        subtitle_font, _hex_to_rgb(subtitle_color),
        shadow=shadow_enabled, max_width=canvas_w - int(160 * scale_f)
    )

    # ── Device frame ──
    frame = DEVICE_FRAMES[frame_name]
    phone_area_top = text_area_h
    phone_area_h = canvas_h - phone_area_top

    # Scale frame to fit phone area nicely
    target_h = int(phone_area_h * phone_scale)
    scale = target_h / frame["height"]
    fw = int(frame["width"] * scale)
    fh = target_h
    fx = (canvas_w - fw) // 2
    fy = phone_area_top + (phone_area_h - fh) // 2 + phone_offset_y

    # Draw device body with shadow
    if shadow_enabled:
        shadow_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow_img)
        br = int(frame["radius"] * scale)
        for offset in range(40, 0, -1):
            alpha = int(180 * (1 - offset / 40))
            _rounded_rect(sdraw, fx - offset//2, fy + offset, fw + offset, fh + offset//2, br, (0, 0, 0, alpha))
        shadow_blurred = shadow_img.filter(ImageFilter.GaussianBlur(20))
        img = Image.alpha_composite(img.convert("RGBA"), shadow_blurred).convert("RGB")
        draw = ImageDraw.Draw(img)

    # Bezel
    br = int(frame["radius"] * scale)
    bezel_color = _hex_to_rgb(frame["color"])
    highlight_color = _hex_to_rgb(frame["highlight"])
    _rounded_rect(draw, fx, fy, fw, fh, br, bezel_color)

    # Highlight rim
    _rounded_rect_outline(draw, fx + 1, fy + 1, fw - 2, fh - 2, br - 1, highlight_color, width=2)

    # Screen bounds
    bz = int(frame["border"] * scale)
    sx, sy = fx + bz, fy + bz
    sw, sh = fw - bz * 2, fh - bz * 2
    sr = max(br - bz, 8)

    # Screenshot inside screen
    if screenshot_bytes:
        try:
            screen_img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
            # Crop/fit to screen area
            img_aspect = screen_img.width / screen_img.height
            screen_aspect = sw / sh
            if img_aspect > screen_aspect:
                new_h = sh
                new_w = int(sh * img_aspect)
            else:
                new_w = sw
                new_h = int(sw / img_aspect)
            screen_img = screen_img.resize((new_w, new_h), Image.LANCZOS)
            crop_x = (new_w - sw) // 2
            crop_y = (new_h - sh) // 2
            screen_img = screen_img.crop((crop_x, crop_y, crop_x + sw, crop_y + sh))

            # Paste with rounded mask
            mask = Image.new("L", (sw, sh), 0)
            mdraw = ImageDraw.Draw(mask)
            _rounded_rect(mdraw, 0, 0, sw, sh, sr, 255)
            img.paste(screen_img, (sx, sy), mask)
            draw = ImageDraw.Draw(img)
        except Exception as e:
            draw.rectangle([sx, sy, sx + sw, sy + sh], fill=(30, 30, 50))
            draw.text((sx + sw // 2, sy + sh // 2), "Screenshot Error", fill=(200, 200, 200), anchor="mm", font=_load_font(32))

    else:
        # Placeholder
        draw.rectangle([sx, sy, sx + sw, sy + sh], fill=(20, 20, 35))
        draw.text((sx + sw // 2, sy + sh // 2), "No Screenshot", fill=(100, 100, 130), anchor="mm", font=_load_font(28))

    # Punch-hole camera
    if frame.get("punch_hole"):
        cam_x = fx + fw // 2
        cam_y = sy + int(sh * 0.028)
        cam_r = int(fw * 0.026)
        draw.ellipse([cam_x - cam_r, cam_y - cam_r, cam_x + cam_r, cam_y + cam_r], fill=bezel_color)
        draw.ellipse([cam_x - cam_r + 3, cam_y - cam_r + 3, cam_x + cam_r - 3, cam_y + cam_r - 3], fill=(10, 10, 10))

    # Side buttons
    btn_color = tuple(max(0, c - 15) for c in bezel_color)
    btn_w = max(4, int(fw * 0.022))
    if frame.get("button_right"):
        # Power button
        draw.rectangle([fx + fw, fy + int(fh * 0.22), fx + fw + btn_w, fy + int(fh * 0.32)], fill=btn_color)
        draw.rectangle([fx - btn_w, fy + int(fh * 0.18), fx, fy + int(fh * 0.26)], fill=btn_color)
        draw.rectangle([fx - btn_w, fy + int(fh * 0.29), fx, fy + int(fh * 0.37)], fill=btn_color)

    return img


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _load_font(size, bold=False):
    _here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(_here, "fonts", "Roboto-Bold.ttf" if bold else "Roboto.ttf"),
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()


def _draw_text_centered(draw, img, text, cx, y, font, color, shadow=True, max_width=900):
    """Draw centered text with optional drop shadow, wrapping if needed."""
    lines = _wrap_text(draw, text, font, max_width)
    try:
        bbox = font.getbbox("Ay")
        line_h = bbox[3] - bbox[1] + 12
    except:
        line_h = font.size + 12

    for i, line in enumerate(lines):
        ly = y + i * line_h
        if shadow:
            draw.text((cx + 3, ly + 3), line, fill=(0, 0, 0, 120) if len(color) == 4 else (0, 0, 0), font=font, anchor="mt")
        draw.text((cx, ly), line, fill=color, font=font, anchor="mt")


def _wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        try:
            w = font.getlength(test)
        except:
            w = len(test) * font.size * 0.6
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _rounded_rect(draw, x, y, w, h, r, color):
    r = min(r, w // 2, h // 2)
    draw.rectangle([x + r, y, x + w - r, y + h], fill=color)
    draw.rectangle([x, y + r, x + w, y + h - r], fill=color)
    draw.ellipse([x, y, x + r * 2, y + r * 2], fill=color)
    draw.ellipse([x + w - r * 2, y, x + w, y + r * 2], fill=color)
    draw.ellipse([x, y + h - r * 2, x + r * 2, y + h], fill=color)
    draw.ellipse([x + w - r * 2, y + h - r * 2, x + w, y + h], fill=color)


def _rounded_rect_outline(draw, x, y, w, h, r, color, width=2):
    r = min(r, w // 2, h // 2)
    draw.arc([x, y, x + r * 2, y + r * 2], 180, 270, fill=color, width=width)
    draw.arc([x + w - r * 2, y, x + w, y + r * 2], 270, 360, fill=color, width=width)
    draw.arc([x, y + h - r * 2, x + r * 2, y + h], 90, 180, fill=color, width=width)
    draw.arc([x + w - r * 2, y + h - r * 2, x + w, y + h], 0, 90, fill=color, width=width)
    draw.line([x + r, y, x + w - r, y], fill=color, width=width)
    draw.line([x + r, y + h, x + w - r, y + h], fill=color, width=width)
    draw.line([x, y + r, x, y + h - r], fill=color, width=width)
    draw.line([x + w, y + r, x + w, y + h - r], fill=color, width=width)


# ─── Color Button ─────────────────────────────────────────────────────────────

class ColorButton(QPushButton):
    color_changed = pyqtSignal(str)

    def __init__(self, color="#ffffff", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(48, 28)
        self._update_style()
        self.clicked.connect(self._pick)

    def _update_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background: {self._color};
                border: 2px solid #444;
                border-radius: 6px;
            }}
            QPushButton:hover {{ border-color: #888; }}
        """)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Pick color")
        if c.isValid():
            self._color = c.name()
            self._update_style()
            self.color_changed.emit(self._color)

    @property
    def color(self):
        return self._color

    def set_color(self, color):
        self._color = color
        self._update_style()


# ─── Main Window ──────────────────────────────────────────────────────────────

class ScreenshotStudioPanel(QWidget):
    logged = pyqtSignal(str)   # consumed by AppWindow → GlobalLogPanel

    def __init__(self):
        super().__init__()

        self._screenshot_bytes = None
        self._devices = []
        self._preview_pil = None
        self._adb_worker = None
        self._plan = []           # screenshots list
        self._plan_devices = []   # devices list
        self._plan_defaults = {}
        self._plan_device_idx = 0
        self._plan_screenshot_idx = 0
        self._plan_dir = ""
        self._plan_output_dir = ""

        self._build_ui()
        self._refresh_devices()
        self._schedule_preview()

    # ── Theme ──────────────────────────────────────────────────────────────

    def _apply_dark_theme(self):
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
            QPushButton:hover { background: #2a2a48; border-color: #6060aa; }
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
            QComboBox QAbstractItemView { background: #1e1e34; color: #eef; selection-background-color: #3d1065; }
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

    # ── UI Construction ────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # Left panel: controls
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(370)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_widget = QWidget()
        left_scroll.setWidget(left_widget)
        self._left_layout = QVBoxLayout(left_widget)
        self._left_layout.setContentsMargins(16, 16, 16, 16)
        self._left_layout.setSpacing(14)
        splitter.addWidget(left_scroll)

        # Right: preview
        right = QWidget()
        right.setStyleSheet("background: #080810;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(right)

        self._build_device_section()
        self._build_background_section()
        self._build_text_section()
        self._build_export_section()
        self._build_batch_section()
        self._build_prefs_section()
        self._left_layout.addStretch()

        # Preview label
        self._preview_label = QLabel("Preview")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("background: #080810; color: #444;")
        self._preview_label.setMinimumWidth(300)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)

        right_layout.addWidget(self._progress)
        right_layout.addWidget(self._preview_label, 1)

        self._log_label = QLabel("Ready.")
        self._log_label.setStyleSheet("color: #667; font-size: 11px; padding: 4px 12px;")
        right_layout.addWidget(self._log_label)

        # Expandable log panel
        self._log_panel = QTextEdit()
        self._log_panel.setReadOnly(True)
        self._log_panel.setFixedHeight(120)
        self._log_panel.setStyleSheet(
            "background:#080810; color:#6a9a6a; font-family:Consolas,monospace;"
            "font-size:11px; border:none; border-top:1px solid #1a1a2e; padding:4px 8px;"
        )
        self._log_panel.setVisible(False)
        right_layout.addWidget(self._log_panel)

        log_toggle = QPushButton("▼ Show Log")
        log_toggle.setFixedHeight(20)
        log_toggle.setStyleSheet(
            "QPushButton{background:#0a0a14; color:#445; border:none; border-top:1px solid #1a1a2e;"
            "font-size:10px;} QPushButton:hover{color:#778;}"
        )
        def _toggle_log():
            visible = not self._log_panel.isVisible()
            self._log_panel.setVisible(visible)
            log_toggle.setText("▲ Hide Log" if visible else "▼ Show Log")
        log_toggle.clicked.connect(_toggle_log)
        right_layout.addWidget(log_toggle)

    def _section(self, title):
        g = QGroupBox(title.upper())
        l = QVBoxLayout(g)
        l.setSpacing(8)
        self._left_layout.addWidget(g)
        return g, l

    def _row(self, label_text, widget, layout):
        row = QHBoxLayout()
        if label_text:
            lbl = QLabel(label_text)
            lbl.setFixedWidth(110)
            lbl.setStyleSheet("color:#8890aa; font-size:12px;")
            row.addWidget(lbl)
        row.addWidget(widget)
        layout.addLayout(row)
        return row

    def _build_device_section(self):
        g, l = self._section("📱 Device & Capture")

        # Refresh + device selector
        dev_row = QHBoxLayout()
        self._device_combo = QComboBox()
        self._device_combo.addItem("No devices found")
        self._device_combo.setMinimumWidth(180)
        self._device_combo.currentIndexChanged.connect(self._on_device_selected)
        self._refresh_btn = QPushButton("⟳ Scan")
        self._refresh_btn.setFixedWidth(70)
        self._refresh_btn.clicked.connect(self._refresh_devices)
        dev_row.addWidget(QLabel("ADB Device:"))
        dev_row.addWidget(self._device_combo, 1)
        dev_row.addWidget(self._refresh_btn)
        l.addLayout(dev_row)

        # Device info badge row
        self._device_info_label = QLabel("")
        self._device_info_label.setStyleSheet("color:#667; font-size:11px; padding:2px 0;")
        self._device_info_label.setWordWrap(True)
        l.addWidget(self._device_info_label)

        # FLAG_SECURE warning (hidden by default)
        self._secure_warning = QLabel(
            "⚠  Black screenshot detected — FLAG_SECURE is active.\n"
            "Use an emulator (no restrictions) or remove FLAG_SECURE\n"
            "from your app's Activity for testing."
        )
        self._secure_warning.setStyleSheet(
            "background:#2a1a00; color:#ffaa44; font-size:11px;"
            "border:1px solid #6b3d00; border-radius:6px; padding:8px;"
        )
        self._secure_warning.setWordWrap(True)
        self._secure_warning.setVisible(False)
        l.addWidget(self._secure_warning)

        # Demo mode
        demo_row = QHBoxLayout()
        self._demo_btn = QPushButton("✨  Clean Status Bar")
        self._demo_btn.setToolTip("Enables Android Demo Mode: fixes time to 12:00, hides notifications, shows full signal/battery.")
        self._demo_btn.clicked.connect(lambda: self._run_demo_mode(True))
        self._demo_exit_btn = QPushButton("↩  Restore Status Bar")
        self._demo_exit_btn.setObjectName("danger")
        self._demo_exit_btn.clicked.connect(lambda: self._run_demo_mode(False))
        self._demo_exit_btn.setVisible(False)
        demo_row.addWidget(self._demo_btn)
        demo_row.addWidget(self._demo_exit_btn)
        l.addLayout(demo_row)

        self._capture_btn = QPushButton("📸  Capture Screenshot from Device")
        self._capture_btn.setObjectName("primary")
        self._capture_btn.clicked.connect(self._capture_screenshot)
        l.addWidget(self._capture_btn)

        import_row = QHBoxLayout()
        import_btn = QPushButton("📂  Import from File")
        import_btn.clicked.connect(self._import_screenshot)
        saved_btn = QPushButton("🕘  Saved")
        saved_btn.setFixedWidth(72)
        saved_btn.setToolTip("Browse previously captured screenshots")
        saved_btn.clicked.connect(self._browse_saved_screenshots)
        import_row.addWidget(import_btn, 1)
        import_row.addWidget(saved_btn)
        l.addLayout(import_row)

        # AVD launcher row (hidden until AVDs are found)
        self._avd_row = QWidget()
        avd_row_layout = QHBoxLayout(self._avd_row)
        avd_row_layout.setContentsMargins(0, 0, 0, 0)
        self._avd_combo = QComboBox()
        self._avd_combo.setMinimumWidth(160)
        self._start_avd_btn = QPushButton("▶  Start")
        self._start_avd_btn.setFixedWidth(70)
        self._start_avd_btn.clicked.connect(self._start_emulator)
        avd_row_layout.addWidget(QLabel("AVD:"))
        avd_row_layout.addWidget(self._avd_combo, 1)
        avd_row_layout.addWidget(self._start_avd_btn)
        self._avd_row.setVisible(False)
        l.addWidget(self._avd_row)

        # Emulator tip
        emu_tip = QLabel("💡 Tip: Emulators never have FLAG_SECURE issues")
        emu_tip.setStyleSheet("color:#445566; font-size:10px; font-style:italic;")
        l.addWidget(emu_tip)

        # Frame selector
        self._frame_combo = QComboBox()
        for name in DEVICE_FRAMES:
            self._frame_combo.addItem(name)
        self._frame_combo.currentTextChanged.connect(self._schedule_preview)
        self._row("Device Frame:", self._frame_combo, l)

        # Phone size slider
        size_row = QHBoxLayout()
        lbl_size = QLabel("Phone Size:")
        lbl_size.setFixedWidth(110)
        lbl_size.setStyleSheet("color:#8890aa; font-size:12px;")
        self._phone_size_slider = QSlider(Qt.Orientation.Horizontal)
        self._phone_size_slider.setRange(40, 150)
        self._phone_size_slider.setValue(150)
        self._phone_size_slider.setTickInterval(10)
        self._phone_size_slider.valueChanged.connect(self._schedule_preview)
        self._phone_size_label = QLabel("150%")
        self._phone_size_label.setFixedWidth(36)
        self._phone_size_label.setStyleSheet("color:#eef; font-size:12px;")
        self._phone_size_slider.valueChanged.connect(
            lambda v: self._phone_size_label.setText(f"{v}%")
        )
        size_row.addWidget(lbl_size)
        size_row.addWidget(self._phone_size_slider, 1)
        size_row.addWidget(self._phone_size_label)
        l.addLayout(size_row)

        # Phone vertical offset slider
        offset_row = QHBoxLayout()
        lbl_offset = QLabel("Vertical Pos:")
        lbl_offset.setFixedWidth(110)
        lbl_offset.setStyleSheet("color:#8890aa; font-size:12px;")
        self._phone_offset_slider = QSlider(Qt.Orientation.Horizontal)
        self._phone_offset_slider.setRange(-500, 500)
        self._phone_offset_slider.setValue(0)
        self._phone_offset_slider.valueChanged.connect(self._schedule_preview)
        self._phone_offset_label = QLabel("0")
        self._phone_offset_label.setFixedWidth(36)
        self._phone_offset_label.setStyleSheet("color:#eef; font-size:12px;")
        self._phone_offset_slider.valueChanged.connect(
            lambda v: self._phone_offset_label.setText(str(v))
        )
        offset_row.addWidget(lbl_offset)
        offset_row.addWidget(self._phone_offset_slider, 1)
        offset_row.addWidget(self._phone_offset_label)
        l.addLayout(offset_row)

        # Screenshot info
        self._shot_info = QLabel("No screenshot loaded")
        self._shot_info.setStyleSheet("color:#556; font-size:11px; padding: 2px 0;")
        l.addWidget(self._shot_info)

    def _build_background_section(self):
        g, l = self._section("🎨 Background")

        # Preset row
        self._preset_combo = QComboBox()
        for name in PRESETS:
            self._preset_combo.addItem(name)
        self._preset_combo.currentTextChanged.connect(self._apply_preset)
        self._row("Preset:", self._preset_combo, l)

        # Color 1
        row1 = QHBoxLayout()
        lbl1 = QLabel("Color Top:")
        lbl1.setFixedWidth(110)
        lbl1.setStyleSheet("color:#8890aa; font-size:12px;")
        self._bg1_btn = ColorButton("#1a0533")
        self._bg1_btn.color_changed.connect(lambda _: self._schedule_preview())
        row1.addWidget(lbl1)
        row1.addWidget(self._bg1_btn)
        row1.addStretch()
        l.addLayout(row1)

        # Color 2
        row2 = QHBoxLayout()
        lbl2 = QLabel("Color Bottom:")
        lbl2.setFixedWidth(110)
        lbl2.setStyleSheet("color:#8890aa; font-size:12px;")
        self._bg2_btn = ColorButton("#3d1065")
        self._bg2_btn.color_changed.connect(lambda _: self._schedule_preview())
        row2.addWidget(lbl2)
        row2.addWidget(self._bg2_btn)
        row2.addStretch()
        l.addLayout(row2)

        # Shadow toggle
        self._shadow_cb = QCheckBox("Device shadow")
        self._shadow_cb.setChecked(True)
        self._shadow_cb.stateChanged.connect(self._schedule_preview)
        l.addWidget(self._shadow_cb)

    def _build_text_section(self):
        g, l = self._section("✏️ Text")

        # Title
        self._title_edit = QLineEdit("Your App Name")
        self._title_edit.textChanged.connect(self._schedule_preview)
        self._row("Title:", self._title_edit, l)

        row_tc = QHBoxLayout()
        lbl = QLabel("Title Style:")
        lbl.setFixedWidth(110)
        lbl.setStyleSheet("color:#8890aa; font-size:12px;")
        self._title_color_btn = ColorButton("#ffffff")
        self._title_color_btn.color_changed.connect(lambda _: self._schedule_preview())
        self._title_size = QSpinBox()
        self._title_size.setRange(20, 160)
        self._title_size.setValue(72)
        self._title_size.setSuffix(" px")
        self._title_size.valueChanged.connect(self._schedule_preview)
        row_tc.addWidget(lbl)
        row_tc.addWidget(self._title_color_btn)
        row_tc.addWidget(QLabel("Size:"))
        row_tc.addWidget(self._title_size)
        l.addLayout(row_tc)

        # Subtitle
        self._sub_edit = QLineEdit("The tagline that sells your app")
        self._sub_edit.textChanged.connect(self._schedule_preview)
        self._row("Subtitle:", self._sub_edit, l)

        row_sc = QHBoxLayout()
        lbl2 = QLabel("Subtitle Style:")
        lbl2.setFixedWidth(110)
        lbl2.setStyleSheet("color:#8890aa; font-size:12px;")
        self._sub_color_btn = ColorButton("#cccccc")
        self._sub_color_btn.color_changed.connect(lambda _: self._schedule_preview())
        self._sub_size = QSpinBox()
        self._sub_size.setRange(12, 100)
        self._sub_size.setValue(38)
        self._sub_size.setSuffix(" px")
        self._sub_size.valueChanged.connect(self._schedule_preview)
        row_sc.addWidget(lbl2)
        row_sc.addWidget(self._sub_color_btn)
        row_sc.addWidget(QLabel("Size:"))
        row_sc.addWidget(self._sub_size)
        l.addLayout(row_sc)

    def _build_export_section(self):
        g, l = self._section("💾 Export")

        res_row = QHBoxLayout()
        lbl = QLabel("Resolution:")
        lbl.setFixedWidth(80)
        lbl.setStyleSheet("color:#8890aa; font-size:12px;")
        self._resolution_combo = QComboBox()
        self._resolution_combo.addItem("1080 × 1920  (HD)",    (1080, 1920))
        self._resolution_combo.addItem("1440 × 2560  (QHD) ★", (1440, 2560))
        self._resolution_combo.addItem("2160 × 3840  (4K)",    (2160, 3840))
        self._resolution_combo.setCurrentIndex(1)
        self._resolution_combo.currentIndexChanged.connect(self._schedule_preview)
        res_row.addWidget(lbl)
        res_row.addWidget(self._resolution_combo, 1)
        l.addLayout(res_row)

        self._export_btn = QPushButton("⬇  Export PNG")
        self._export_btn.setObjectName("primary")
        self._export_btn.clicked.connect(self._export)
        l.addWidget(self._export_btn)

    def _build_batch_section(self):
        g, l = self._section("📋 Batch Plan")

        load_btn = QPushButton("📂  Load Plan (JSON)")
        load_btn.clicked.connect(self._load_plan)
        l.addWidget(load_btn)

        hint = QLabel('Format: [{"title":"...", "subtitle":"...", "preset":"Ocean Blue", "filename":"01.png"}, ...]')
        hint.setStyleSheet("color:#445566; font-size:10px;")
        hint.setWordWrap(True)
        l.addWidget(hint)

        # Step panel — hidden until plan loaded
        self._batch_widget = QWidget()
        bl = QVBoxLayout(self._batch_widget)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)

        self._batch_device_label = QLabel("")
        self._batch_device_label.setStyleSheet("color:#7c3aed; font-size:12px; font-weight:bold;")
        bl.addWidget(self._batch_device_label)

        self._batch_step_label = QLabel("")
        self._batch_step_label.setStyleSheet("color:#eef; font-size:12px;")
        bl.addWidget(self._batch_step_label)

        self._batch_item_label = QLabel("")
        self._batch_item_label.setStyleSheet("color:#aab; font-size:11px;")
        self._batch_item_label.setWordWrap(True)
        bl.addWidget(self._batch_item_label)

        nav_row = QHBoxLayout()
        self._batch_prev_btn = QPushButton("◀ Prev")
        self._batch_prev_btn.clicked.connect(lambda: self._plan_goto(self._plan_linear() - 1))
        self._batch_next_btn = QPushButton("Next ▶")
        self._batch_next_btn.clicked.connect(lambda: self._plan_goto(self._plan_linear() + 1))
        clear_btn = QPushButton("✕")
        clear_btn.setFixedWidth(32)
        clear_btn.setToolTip("Clear plan")
        clear_btn.clicked.connect(self._clear_plan)
        nav_row.addWidget(self._batch_prev_btn)
        nav_row.addWidget(self._batch_next_btn)
        nav_row.addStretch()
        nav_row.addWidget(clear_btn)
        bl.addLayout(nav_row)

        self._batch_widget.setVisible(False)
        l.addWidget(self._batch_widget)

    def _build_prefs_section(self):
        from app.tools.copy_prefs_panel import CopyPrefsPanel
        g, l = self._section("🔁 Copy Preferences")
        self._copy_prefs_panel = CopyPrefsPanel(compact=True)
        l.addWidget(self._copy_prefs_panel)

    # ── Logic ──────────────────────────────────────────────────────────────

    def _refresh_devices(self):
        self._log("Scanning ADB devices...")
        self._device_combo.clear()
        worker = ADBWorker("list")
        worker.devices_found.connect(self._on_devices_found)
        worker.avds_found.connect(self._on_avds_found)
        worker.error.connect(self._on_adb_error)
        worker.log.connect(self._log)
        self._adb_worker = worker
        worker.start()

    def _on_devices_found(self, devices):
        self._devices = devices
        self._device_combo.clear()
        if devices:
            for d in devices:
                if d["is_emulator"]:
                    label = f"🖥  {d['avd_name'] or d['model']}  ({d['serial']})"
                else:
                    label = f"📱  {d['model']}  ({d['serial']})"
                self._device_combo.addItem(
                    label.replace("(", "[Emulator]  (" if d["is_emulator"] else "[Physical]  ("),
                    d["serial"]
                )
            self._on_device_selected(0)
        else:
            self._device_combo.addItem("No devices — connect via USB or start an emulator")
            self._device_info_label.setText("")
        # Sync device list into the embedded Copy Prefs panel
        self._copy_prefs_panel.set_devices(devices)

    def _on_device_selected(self, index):
        """Update device info badge when selection changes."""
        if not self._devices or index < 0 or index >= len(self._devices):
            self._device_info_label.setText("")
            return
        d = self._devices[index]
        parts = []
        if d["android_ver"]:
            parts.append(f"Android {d['android_ver']}")
        if d["resolution"]:
            parts.append(d["resolution"])
        if d["is_emulator"]:
            parts.append("✓ No FLAG_SECURE restrictions")
            self._device_info_label.setStyleSheet("color:#3a8a3a; font-size:11px; padding:2px 0;")
        else:
            parts.append("Physical — FLAG_SECURE may apply")
            self._device_info_label.setStyleSheet("color:#667; font-size:11px; padding:2px 0;")
        self._device_info_label.setText("  ·  ".join(parts))

        # Auto-suggest device frame based on model name
        model_lower = d["model"].lower()
        avd_lower = (d.get("avd_name") or "").lower()
        combined = model_lower + avd_lower
        if "pixel" in combined and ("tablet" in combined or "tab" in combined):
            self._frame_combo.setCurrentText("Pixel Tablet")
        elif "tablet" in combined or "tab" in combined or "pad" in combined:
            self._frame_combo.setCurrentText("Generic Tablet")
        elif "pixel" in combined:
            self._frame_combo.setCurrentText("Pixel 8")
        elif "samsung" in combined or "galaxy" in combined:
            self._frame_combo.setCurrentText("Samsung S24")

    def _on_avds_found(self, avds):
        self._avd_combo.clear()
        if avds:
            for name in avds:
                self._avd_combo.addItem(name)
            self._avd_row.setVisible(True)
        else:
            self._avd_row.setVisible(False)

    def _start_emulator(self):
        avd_name = self._avd_combo.currentText()
        if not avd_name:
            return
        self._start_avd_btn.setEnabled(False)
        self._progress.setVisible(True)
        worker = EmulatorStartWorker(avd_name)
        worker.log.connect(self._log)
        worker.error.connect(lambda msg: (
            self._on_adb_error(msg),
            self._start_avd_btn.setEnabled(True),
            self._progress.setVisible(False),
        ))
        worker.device_ready.connect(self._on_emulator_ready)
        self._emu_worker = worker
        worker.start()

    def _on_emulator_ready(self):
        self._start_avd_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._refresh_devices()

    def _on_adb_error(self, msg):
        self._log(f"⚠ {msg}")
        QMessageBox.warning(self, "ADB Error", msg)

    def _capture_screenshot(self):
        if not self._devices:
            QMessageBox.information(self, "No Device", "No ADB device found.\n\nMake sure:\n• USB debugging is ON\n• Device is connected\n• adb.exe is in PATH")
            return
        serial = self._device_combo.currentData()
        if not serial:
            return
        self._progress.setVisible(True)
        self._capture_btn.setEnabled(False)
        self._secure_warning.setVisible(False)
        self._log("Capturing screenshot...")

        worker = ADBWorker("screenshot", device_id=serial)
        worker.screenshot_done.connect(self._on_screenshot_done)
        worker.error.connect(self._on_adb_error)
        worker.log.connect(self._log)
        worker.secure_flag_warning.connect(self._on_secure_flag_warning)
        worker.finished.connect(lambda: (
            self._progress.setVisible(False),
            self._capture_btn.setEnabled(True)
        ))
        self._adb_worker = worker
        worker.start()

    def _on_secure_flag_warning(self):
        self._secure_warning.setVisible(True)
        self._log("⚠ Black screenshot — FLAG_SECURE detected.")

    def _run_demo_mode(self, enable):
        serial = self._device_combo.currentData()
        if not serial:
            QMessageBox.information(self, "No Device", "Select a device first.")
            return

        def shell(cmd):
            subprocess.run(["adb", "-s", serial, "shell"] + cmd,
                           capture_output=True, timeout=10)

        if enable:
            shell(["settings", "put", "global", "sysui_demo_allowed", "1"])
            shell(["am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", "enter"])
            shell(["am", "broadcast", "-a", "com.android.systemui.demo",
                   "-e", "command", "clock", "-e", "hhmm", "1200"])
            shell(["am", "broadcast", "-a", "com.android.systemui.demo",
                   "-e", "command", "notifications", "-e", "visible", "false"])
            shell(["am", "broadcast", "-a", "com.android.systemui.demo",
                   "-e", "command", "battery", "-e", "plugged", "false", "-e", "level", "100"])
            shell(["am", "broadcast", "-a", "com.android.systemui.demo",
                   "-e", "command", "network",
                   "-e", "wifi", "show", "-e", "level", "4", "-e", "fully", "true",
                   "-e", "mobile", "hide"])
            self._log("Demo mode ON — 12:00, no notifications, full signal.")
            self._demo_btn.setVisible(False)
            self._demo_exit_btn.setVisible(True)
        else:
            shell(["am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", "exit"])
            self._log("Demo mode OFF.")
            self._demo_btn.setVisible(True)
            self._demo_exit_btn.setVisible(False)

    def _load_plan(self):
        import json
        path, _ = QFileDialog.getOpenFileName(self, "Load Plan", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path) as f:
                raw = json.load(f)
            if isinstance(raw, list):
                self._plan_defaults = {}
                self._plan_devices = [{}]   # single anonymous device
                self._plan = raw
                self._plan_output_dir = ""
            else:
                self._plan_defaults = raw.get("defaults", {})
                self._plan_devices = raw.get("devices", [{}])
                self._plan = raw.get("screenshots", [])
                self._plan_output_dir = raw.get("output_dir", "")
            self._plan_dir = os.path.dirname(path)
            self._plan_device_idx = 0
            self._plan_screenshot_idx = 0
            self._plan_apply_step(0, 0)
            self._batch_widget.setVisible(True)
            total = len(self._plan_devices) * len(self._plan)
            self._log(f"Plan loaded: {len(self._plan_devices)} device(s) × {len(self._plan)} screenshots = {total} total.")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def _plan_linear(self):
        return self._plan_device_idx * len(self._plan) + self._plan_screenshot_idx

    def _plan_total(self):
        return len(self._plan_devices) * len(self._plan)

    def _plan_goto(self, linear):
        if not self._plan or not self._plan_devices:
            return
        linear = max(0, min(linear, self._plan_total() - 1))
        device_idx = linear // len(self._plan)
        screenshot_idx = linear % len(self._plan)
        self._plan_apply_step(device_idx, screenshot_idx)

    def _plan_apply_step(self, device_idx, screenshot_idx):
        self._plan_device_idx = device_idx
        self._plan_screenshot_idx = screenshot_idx

        device = self._plan_devices[device_idx]
        shot = self._plan[screenshot_idx]
        cfg = {**self._plan_defaults, **device, **shot}

        # Device label
        device_name = device.get("name") or device.get("fastlane_dir") or f"Device {device_idx + 1}"
        self._batch_device_label.setText(
            f"{device_name}  ({device_idx + 1} / {len(self._plan_devices)})"
        )
        self._batch_step_label.setText(
            f"Screenshot {screenshot_idx + 1} / {len(self._plan)}  —  {cfg.get('filename', '')}"
        )
        self._batch_item_label.setText(f"{cfg.get('title', '')}\n{cfg.get('subtitle', '')}")

        linear = self._plan_linear()
        self._batch_prev_btn.setEnabled(linear > 0)
        self._batch_next_btn.setEnabled(linear < self._plan_total() - 1)

        if cfg.get("title") is not None:
            self._title_edit.setText(cfg["title"])
        if cfg.get("subtitle") is not None:
            self._sub_edit.setText(cfg["subtitle"])
        if cfg.get("title_size"):
            self._title_size.setValue(cfg["title_size"])
        if cfg.get("subtitle_size"):
            self._sub_size.setValue(cfg["subtitle_size"])
        if cfg.get("title_color"):
            self._title_color_btn.set_color(cfg["title_color"])
        if cfg.get("subtitle_color"):
            self._sub_color_btn.set_color(cfg["subtitle_color"])
        if cfg.get("phone_size"):
            self._phone_size_slider.setValue(cfg["phone_size"])
        if cfg.get("phone_offset_y") is not None:
            self._phone_offset_slider.setValue(cfg["phone_offset_y"])
        if cfg.get("shadow") is not None:
            self._shadow_cb.setChecked(cfg["shadow"])
        if cfg.get("frame") and cfg["frame"] in DEVICE_FRAMES:
            self._frame_combo.setCurrentText(cfg["frame"])
        if cfg.get("canvas_w") and cfg.get("canvas_h"):
            for i in range(self._resolution_combo.count()):
                if self._resolution_combo.itemData(i) == (cfg["canvas_w"], cfg["canvas_h"]):
                    self._resolution_combo.setCurrentIndex(i)
                    break
        preset = cfg.get("preset")
        if preset and preset in PRESETS:
            self._preset_combo.setCurrentText(preset)
        elif cfg.get("bg_color1"):
            self._bg1_btn.set_color(cfg["bg_color1"])
            self._bg2_btn.set_color(cfg.get("bg_color2", cfg["bg_color1"]))
        self._schedule_preview()

    def _clear_plan(self):
        self._plan = []
        self._plan_devices = []
        self._plan_defaults = {}
        self._plan_device_idx = 0
        self._plan_screenshot_idx = 0
        self._plan_dir = ""
        self._plan_output_dir = ""
        self._batch_widget.setVisible(False)
        self._log("Plan cleared.")

    def _plan_auto_export(self, kwargs, path):
        current_linear = self._plan_linear()
        total = self._plan_total()
        def _run():
            try:
                img = compose_image(**kwargs)
                img.save(path, "PNG", optimize=True)
                rel = os.path.relpath(path, self._plan_dir)
                self._log(f"✓ Saved: {rel}  ({current_linear + 1}/{total})")
                next_linear = current_linear + 1
                if next_linear < total:
                    QTimer.singleShot(600, lambda: self._plan_goto(next_linear))
                else:
                    QTimer.singleShot(600, lambda: self._log("✓ Batch complete! All devices done."))
            except Exception as e:
                self._log(f"Auto-export failed: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def _save_raw_screenshot(self, data):
        """Save raw capture to screenshots/ for later reuse."""
        try:
            from datetime import datetime
            shots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
            os.makedirs(shots_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(shots_dir, f"capture_{ts}.png")
            with open(path, "wb") as f:
                f.write(data)
            self._log(f"✓ Capture saved: screenshots/capture_{ts}.png")
        except Exception as e:
            self._log(f"Could not save capture: {e}")

    def _on_screenshot_done(self, data):
        self._screenshot_bytes = data
        self._save_raw_screenshot(data)
        try:
            img = Image.open(io.BytesIO(data))
            self._shot_info.setText(f"✓ Screenshot: {img.width}×{img.height}px")
        except:
            self._shot_info.setText("✓ Screenshot captured")
        self._log("Screenshot ready. Updating preview...")
        self._schedule_preview()

        if self._plan and self._plan_devices:
            di, si = self._plan_device_idx, self._plan_screenshot_idx
            device = self._plan_devices[di]
            shot = self._plan[si]
            cfg = {**self._plan_defaults, **device, **shot}
            filename = cfg.get("filename", f"screenshot_{si + 1:02d}.png")
            fastlane_dir = device.get("fastlane_dir", device.get("name", f"device{di+1}"))
            out_dir = getattr(self, "_plan_output_dir", "")
            base = os.path.join(self._plan_dir, out_dir, fastlane_dir)
            os.makedirs(base, exist_ok=True)
            path = os.path.join(base, filename)
            kwargs = self._get_compose_kwargs()
            self._plan_auto_export(kwargs, path)

    def _browse_saved_screenshots(self):
        shots_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
        os.makedirs(shots_dir, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(
            self, "Saved Screenshots", shots_dir,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._load_screenshot_file(path)

    def _load_screenshot_file(self, path):
        with open(path, "rb") as f:
            self._screenshot_bytes = f.read()
        try:
            img = Image.open(io.BytesIO(self._screenshot_bytes))
            self._shot_info.setText(f"✓ {Path(path).name}  {img.width}×{img.height}px")
        except:
            self._shot_info.setText(f"✓ {Path(path).name}")
        self._log(f"Loaded: {Path(path).name}")
        self._schedule_preview()

    def _import_screenshot(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Screenshot", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._load_screenshot_file(path)

    def _apply_preset(self, name):
        colors = PRESETS.get(name)
        if colors:
            self._bg1_btn.set_color(colors[0])
            self._bg2_btn.set_color(colors[1])
            self._schedule_preview()

    def _schedule_preview(self, *_):
        """Debounce preview updates."""
        if hasattr(self, "_preview_timer"):
            self._preview_timer.stop()
        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start(250)

    def _get_compose_kwargs(self):
        return dict(
            screenshot_bytes=self._screenshot_bytes,
            frame_name=self._frame_combo.currentText(),
            bg_color1=self._bg1_btn.color,
            bg_color2=self._bg2_btn.color,
            title_text=self._title_edit.text() or " ",
            subtitle_text=self._sub_edit.text() or " ",
            title_color=self._title_color_btn.color,
            subtitle_color=self._sub_color_btn.color,
            title_size=self._title_size.value(),
            subtitle_size=self._sub_size.value(),
            shadow_enabled=self._shadow_cb.isChecked(),
            phone_scale=self._phone_size_slider.value() / 100,
            phone_offset_y=self._phone_offset_slider.value(),
            canvas_w=self._resolution_combo.currentData()[0],
            canvas_h=self._resolution_combo.currentData()[1],
        )

    def _update_preview(self):
        try:
            pil_img = compose_image(**self._get_compose_kwargs())
            self._preview_pil = pil_img

            # Scale to fit preview area
            avail_w = self._preview_label.width() - 20
            avail_h = self._preview_label.height() - 20
            scale = min(avail_w / CANVAS_W, avail_h / CANVAS_H)
            pw = int(CANVAS_W * scale)
            ph = int(CANVAS_H * scale)
            thumb = pil_img.resize((pw, ph), Image.LANCZOS)

            # Convert to QPixmap
            buf = io.BytesIO()
            thumb.save(buf, format="PNG")
            pixmap = QPixmap()
            pixmap.loadFromData(buf.getvalue())
            self._preview_label.setPixmap(pixmap)
            self._log("Preview updated.")
        except Exception as e:
            self._log(f"Preview error: {e}")

    def _export(self):
        if self._preview_pil is None:
            self._update_preview()

        path, _ = QFileDialog.getSaveFileName(
            self, "Export PNG", "play_store_screenshot.png",
            "PNG Image (*.png)"
        )
        if not path:
            return

        self._progress.setVisible(True)
        self._export_btn.setEnabled(False)
        self._log("Exporting full-resolution PNG...")

        def _do_export():
            try:
                img = compose_image(**self._get_compose_kwargs())
                img.save(path, "PNG", optimize=True)
                return True, path
            except Exception as e:
                return False, str(e)

        def _run():
            ok, result = _do_export()
            if ok:
                self._log(f"✓ Exported: {result}")
                QTimer.singleShot(0, lambda: QMessageBox.information(
                    self, "Export Complete",
                    f"Saved to:\n{result}\n\n1080 × 1920 px — Store listing ready ✓"
                ))
            else:
                self._log(f"Export failed: {result}")
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Export Failed", result))
            QTimer.singleShot(0, lambda: (
                self._progress.setVisible(False),
                self._export_btn.setEnabled(True)
            ))

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def _log(self, msg):
        from datetime import datetime
        self._log_label.setText(msg)
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_panel.append(f"[{ts}] {msg}")
        self._log_panel.verticalScrollBar().setValue(
            self._log_panel.verticalScrollBar().maximum()
        )
        self.logged.emit(msg)   # → GlobalLogPanel

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_preview()


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    from app.window import AppWindow, set_app_icon
    from app.tools.copy_prefs_panel import CopyPrefsPanel
    from app.tools.settings_page import SettingsPage
    from app.tools.config_viewer_panel import ConfigViewerPanel
    app = QApplication(sys.argv)
    app.setApplicationName("App Listing Studio")
    app.setStyle("Fusion")
    set_app_icon(app)
    win = AppWindow()

    panel = ScreenshotStudioPanel()
    win.register_tool("screenshot_studio", "📸", "Screenshot Studio", panel)

    # Copy Preferences — centred in its own tool page
    cp_page = QWidget()
    cp_layout = QHBoxLayout(cp_page)
    cp_layout.setContentsMargins(0, 0, 0, 0)
    cp_panel = CopyPrefsPanel(compact=False)
    cp_panel.setMaximumWidth(560)
    cp_layout.addStretch()
    cp_layout.addWidget(cp_panel)
    cp_layout.addStretch()
    win.register_tool("copy_prefs", "🔁", "Copy Preferences", cp_page)
    cp_panel.logged.connect(win.log)

    # Config Viewer
    config_viewer = ConfigViewerPanel()
    win.register_tool("config_viewer", "🗂", "Config Viewer", config_viewer)

    # Settings — pinned to the bottom of the sidebar
    win.register_pinned("settings", "⚙", "Settings", SettingsPage())

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
