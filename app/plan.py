"""
Plan — the JSON template that describes a store listing.

Shape (every key optional except screenshots):
{
  "app":       {"name", "developer", "icon", "rating", "short_description", "description"},
  "input_dir": "raw/{locale}/phone",   # raw screenshots, relative to the plan file ("source_dir" also works)
  "output_dir": "fastlane/...",
  "defaults":  {...},                  # style keys shared by every image
  "devices":   [{"name", "frame", "canvas_w", "canvas_h", "input_dir", ...}],
  "screenshots": [{"filename", "source", "title", "subtitle", ...}],
  "locales":   {"en-US": [{"filename", "title", "subtitle"}], "sv-SE": [...]}
}

Per-image config = defaults ← device ← screenshot ← locale entry (later wins).
"{locale}" in input_dir / output_dir is replaced by the selected locale.
Listing text and icon not given under "app" come from fastlane metadata (see listing.py).
A bare JSON list is treated as just the screenshots.
"""

import json
import os
import sys
from dataclasses import dataclass, field

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from main import DEVICE_FRAMES, PRESETS, FONT_FAMILIES  # noqa: E402

@dataclass
class Plan:
    path: str
    app: dict = field(default_factory=dict)
    defaults: dict = field(default_factory=dict)
    devices: list = field(default_factory=lambda: [{}])
    screenshots: list = field(default_factory=list)
    input_dir: str = ""
    output_dir: str = ""
    locales: dict = field(default_factory=dict)
    locale: str = ""

    @property
    def dir(self) -> str:
        return os.path.dirname(self.path)

    def _sub(self, s: str) -> str:
        return s.replace("{locale}", self.locale) if s else s

    def shots(self) -> list:
        """Screenshots with the selected locale's text merged in (matched by filename)."""
        by_name = {t.get("filename"): t for t in self.locales.get(self.locale, [])}
        return [{**s, **by_name.get(s.get("filename"), {})} for s in self.screenshots]

    def cfg(self, device: dict, shot: dict) -> dict:
        cfg = {**self.defaults, **device, **shot}
        font = cfg.get("font")
        if font and font not in FONT_FAMILIES:
            cfg["font"] = os.path.normpath(os.path.join(self.dir, font))
        return cfg

    def device_name(self, idx: int) -> str:
        d = self.devices[idx]
        return d.get("name") or d.get("fastlane_dir") or f"Device {idx + 1}"

    def platform(self, device: dict) -> str:
        """"ios" or "android" — explicit "platform" key, else from the frame."""
        if device.get("platform"):
            return device["platform"]
        frame = DEVICE_FRAMES.get({**self.defaults, **device}.get("frame", ""), {})
        return frame.get("platform", "android")

    def source_path(self, cfg: dict, override_dir: str = "") -> str:
        """Raw screenshot for one image: <input_dir>/<source or filename>."""
        name = cfg.get("source") or cfg.get("filename", "")
        if not name:
            return ""
        base = override_dir or self._sub(cfg.get("input_dir") or cfg.get("source_dir") or self.input_dir)
        return os.path.normpath(os.path.join(self.dir, base, name))

    def app_info(self, platform: str) -> dict:
        """The plan's own "app" block (icon resolved against the plan dir); fastlane text is merged in by listing.py."""
        info = {k: v for k, v in self.app.items() if v}
        if info.get("icon") and not os.path.isabs(info["icon"]):
            info["icon"] = os.path.join(self.dir, info["icon"])
        return info


def load_plan(path: str, locale: str = "") -> Plan:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return Plan(path=path, screenshots=raw)
    locales = raw.get("locales") or {}
    return Plan(
        path=path,
        app=raw.get("app", {}),
        defaults=raw.get("defaults", {}),
        devices=raw.get("devices") or [{}],
        screenshots=raw.get("screenshots", []),
        input_dir=raw.get("input_dir") or raw.get("source_dir", ""),
        output_dir=raw.get("output_dir", ""),
        locales=locales,
        locale=locale if locale in locales else next(iter(locales), ""),
    )


def compose_kwargs(cfg: dict, screenshot_bytes, render_w: int | None = None) -> dict:
    """compose_image() kwargs for one merged config; render_w scales the canvas down for previews."""
    preset = cfg.get("preset")
    if preset in PRESETS and PRESETS[preset]:
        bg1, bg2 = PRESETS[preset]
    else:
        bg1 = cfg.get("bg_color1", "#1a0533")
        bg2 = cfg.get("bg_color2", bg1)

    frame = cfg.get("frame")
    if frame not in DEVICE_FRAMES:
        frame = next(iter(DEVICE_FRAMES))
    default_canvas = DEVICE_FRAMES[frame].get("canvas", (1440, 2560))
    canvas_w = cfg.get("canvas_w", default_canvas[0])
    canvas_h = cfg.get("canvas_h", default_canvas[1])
    scale = render_w / canvas_w if render_w else 1.0

    bars = cfg.get("android_bars")
    return dict(
        screenshot_bytes=screenshot_bytes,
        frame_name=frame,
        bg_color1=bg1,
        bg_color2=bg2,
        title_text=cfg.get("title") or " ",
        subtitle_text=cfg.get("subtitle") or " ",
        title_color=cfg.get("title_color", "#ffffff"),
        subtitle_color=cfg.get("subtitle_color", "#cccccc"),
        title_size=cfg.get("title_size", 72),
        subtitle_size=cfg.get("subtitle_size", 38),
        shadow_enabled=cfg.get("shadow", True),
        phone_scale=cfg.get("phone_size", 150) / 100,
        phone_offset_y=int(cfg.get("phone_offset_y", 0) * scale),
        canvas_w=round(canvas_w * scale),
        canvas_h=round(canvas_h * scale),
        bg_style=cfg.get("bg_style", "Gradient"),
        ground_at=cfg.get("ground_at", 72) / 100,
        noise=cfg.get("noise", True),
        text_shadow=cfg.get("text_shadow"),
        font_family=cfg.get("font", "Roboto"),
        title_weight=cfg.get("title_weight", 700),
        subtitle_weight=cfg.get("subtitle_weight", 400),
        tracking=cfg.get("tracking", 0.0),
        android_bars=tuple(bars) if bars else None,
        ios_native=cfg.get("ios_native", False),
    )
