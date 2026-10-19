"""
Plan checks — does a plan produce good store images, before any screenshot exists?

check_plan(plan, devices) → [Issue], one list for the plan and every image
(device × screenshot) it would render. The layout is measured at full canvas
size with the same formulas as compose_image() in main.py; keep layout() in
step with it.

Store rules (2026):
  Google Play  each side 320–3840 px, long side ≤ 2× short side, 2–8 per device type;
               7"/10" tablets 1080–7680 px per side.
  App Store    exact sizes per display class (APP_STORE_SIZES), 1–10 per device.
"""

import os
import re
from dataclasses import dataclass

from main import DEVICE_FRAMES, PRESETS, FONT_FAMILIES, _load_font, _wrap_text, _line_width

ERROR, WARN = "error", "warn"

# App Store Connect accepted portrait sizes → display class
APP_STORE_SIZES = {
    (1320, 2868): "iPhone 6.9\"", (1290, 2796): "iPhone 6.9\"", (1260, 2736): "iPhone 6.9\"",
    (1284, 2778): "iPhone 6.5\"", (1242, 2688): "iPhone 6.5\"",
    (1206, 2622): "iPhone 6.3\"", (1179, 2556): "iPhone 6.3\"",
    (1170, 2532): "iPhone 6.1\"", (1125, 2436): "iPhone 6.1\"", (1080, 2340): "iPhone 6.1\"",
    (1242, 2208): "iPhone 5.5\"",
    (2064, 2752): "iPad 13\"", (2048, 2732): "iPad 13\"",
    (1668, 2420): "iPad 11\"", (1668, 2388): "iPad 11\"", (1640, 2360): "iPad 11\"", (1488, 2266): "iPad 11\"",
}

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass
class Issue:
    level: str          # ERROR | WARN
    message: str
    device: str = ""    # "" = whole plan
    shot: int = -1      # -1 = whole device


# ─── Layout (mirrors compose_image) ───────────────────────────────────────────

def layout(kw: dict) -> dict:
    """Full-size geometry of one image from its compose_image kwargs."""
    W, H = kw["canvas_w"], kw["canvas_h"]
    text_area_h = int(H * 0.38)
    scale_f = W / 1440
    title_px = int(kw["title_size"] * scale_f)
    sub_px = int(kw["subtitle_size"] * scale_f)
    title_font = _load_font(title_px, bold=True, family=kw["font_family"], weight=kw["title_weight"])
    sub_font = _load_font(sub_px, bold=False, family=kw["font_family"], weight=kw["subtitle_weight"])
    tracking = kw.get("tracking", 0.0) * title_px

    def block(text, font, y, max_w, track):
        lines = _wrap_text(None, text, font, max_w, track)
        try:
            b = font.getbbox("Ay")
            line_h = b[3] - b[1] + 12
        except Exception:
            line_h = font.size + 12
        widths = [_line_width(font, l, track) for l in lines]
        return dict(lines=lines, top=y, bottom=y + len(lines) * line_h, max_w=max_w,
                    width=max(widths, default=0))

    title_y = int(text_area_h * 0.28)
    title = block(kw["title_text"], title_font, title_y, W - int(120 * scale_f), tracking)
    sub_y = max(title_y + title_px + int(28 * scale_f), title["bottom"] + int(16 * scale_f))
    sub = block(kw["subtitle_text"], sub_font, sub_y, W - int(160 * scale_f), 0)

    frame = DEVICE_FRAMES[kw["frame_name"]]
    phone_area_h = H - text_area_h
    fh = int(phone_area_h * kw["phone_scale"])
    s = fh / frame["height"]
    fw = int(frame["width"] * s)
    fx = (W - fw) // 2
    fy = text_area_h + (phone_area_h - fh) // 2 + kw["phone_offset_y"]
    return dict(W=W, H=H, title=title, sub=sub, frame=(fx, fy, fw, fh),
                title_font=title_font, sub_font=sub_font)


# ─── Colour ───────────────────────────────────────────────────────────────────

def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _bg_at(kw, y):
    c1, c2 = _rgb(kw["bg_color1"]), _rgb(kw["bg_color2"])
    if kw.get("bg_style") == "Ground":
        return c1 if y < kw["canvas_h"] * kw.get("ground_at", 0.72) else c2
    t = y / kw["canvas_h"]
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def contrast(a, b):
    def lum(c):
        ch = [v / 255 for v in c]
        ch = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ─── Checks ───────────────────────────────────────────────────────────────────

def _font_issues(cfg):
    font = cfg.get("font", "Roboto")
    if font in FONT_FAMILIES:
        if FONT_FAMILIES[font] is None:   # Roboto: bundled files, else system fallbacks
            loaded = _load_font(40, bold=True, family=font)
            name = " ".join(loaded.getname()) if hasattr(loaded, "getname") else "Pillow's bitmap font"
            if "Roboto" not in name:
                return [Issue(WARN, f"Font \"Roboto\" can't be loaded (fonts/Roboto*.ttf are not font files) — "
                                    f"renders with {name}")]
        return []
    if not os.path.isfile(font):
        return [Issue(ERROR, f"Font file not found: {font} — renders with the fallback font")]
    try:
        from PIL import ImageFont
        ImageFont.truetype(font, 40)
    except Exception as e:
        return [Issue(ERROR, f"Font can't be loaded ({e}): {os.path.basename(font)}")]
    return []


def _style_issues(cfg):
    out = []
    if cfg.get("frame") and cfg["frame"] not in DEVICE_FRAMES:
        out.append(Issue(ERROR, f"Unknown frame \"{cfg['frame']}\" — falls back to {next(iter(DEVICE_FRAMES))}. "
                                f"Known: {', '.join(DEVICE_FRAMES)}"))
    elif not cfg.get("frame"):
        out.append(Issue(WARN, f"No frame set — uses {next(iter(DEVICE_FRAMES))}"))
    preset = cfg.get("preset")
    if preset and preset not in PRESETS:
        out.append(Issue(WARN, f"Unknown preset \"{preset}\" — uses bg_color1/bg_color2"))
    for key in ("bg_color1", "bg_color2", "title_color", "subtitle_color"):
        v = cfg.get(key)
        if v is not None and not (isinstance(v, str) and _HEX.match(v)):
            out.append(Issue(ERROR, f"{key} \"{v}\" is not a #rrggbb colour — the render fails"))
    return out


def _store_issues(platform, device_name, W, H, count, frame):
    out = []
    short, long_ = min(W, H), max(W, H)
    if platform == "ios":
        cls = APP_STORE_SIZES.get((short, long_))
        if not cls:
            near = ", ".join(f"{w}×{h}" for (w, h), c in APP_STORE_SIZES.items()
                             if c.startswith("iPad") == bool(frame.get("tablet")))
            out.append(Issue(ERROR, f"{W}×{H} is not an App Store size — App Store Connect rejects it. "
                                    f"Accepted: {near}", device_name))
        if not 1 <= count <= 10:
            out.append(Issue(ERROR, f"{count} screenshots — the App Store takes 1 to 10", device_name))
    else:
        tablet = "tablet" in device_name.lower() or "inch" in device_name.lower()
        lo, hi = (1080, 7680) if tablet else (320, 3840)
        if short < lo or long_ > hi:
            out.append(Issue(ERROR, f"{W}×{H}: Google Play needs each side between {lo} and {hi} px", device_name))
        if long_ > 2 * short:
            out.append(Issue(ERROR, f"{W}×{H}: Google Play rejects a long side over 2× the short side", device_name))
        if not tablet and short < 1080:
            out.append(Issue(WARN, f"{W}×{H}: under 1080 px wide — not eligible for Play's promoted placements",
                             device_name))
        if not 2 <= count <= 8:
            out.append(Issue(ERROR, f"{count} screenshots — Google Play takes 2 to 8 per device type", device_name))
    return out


def check_image(kw, device_name, shot_idx):
    """Issues for one rendered image (compose_image kwargs at full size)."""
    out = []

    def add(level, msg):
        out.append(Issue(level, msg, device_name, shot_idx))

    if kw["frame_name"] not in DEVICE_FRAMES:
        return out
    try:
        g = layout(kw)
    except Exception as e:
        add(ERROR, f"Layout failed: {e}")
        return out
    W, H = g["W"], g["H"]
    t, s = g["title"], g["sub"]
    fx, fy, fw, fh = g["frame"]
    has_title = kw["title_text"].strip() != ""
    has_sub = kw["subtitle_text"].strip() != ""

    if not has_title:
        add(WARN, "No title")
    for name, blk, font in (("Title", t, g["title_font"]), ("Subtitle", s, g["sub_font"])):
        if not blk["lines"] or not blk["lines"][0].strip():
            continue
        if blk["width"] > blk["max_w"]:
            wide = max(blk["lines"], key=lambda l: font.getlength(l))
            add(ERROR, f"{name}: \"{wide}\" is wider than the text area and gets cut at the edges")
        if len(blk["lines"]) > 2:
            add(WARN, f"{name} wraps to {len(blk['lines'])} lines")

    text_bottom = s["bottom"] if has_sub else t["bottom"]
    gap = fy - text_bottom
    if gap < 0:
        add(ERROR, f"Text runs into the device by {-gap} px — lower phone_offset_y or shorten the text")
    elif gap < H * 0.015:
        add(WARN, f"Only {gap} px between the text and the device")

    if fw > W:
        add(ERROR, f"Device ({fw} px) is wider than the canvas ({W} px) — lower phone_size")
    elif fx < W * 0.04:
        add(WARN, "Device almost touches the side edges — lower phone_size")
    if fy < 0:
        add(ERROR, "Device starts above the top of the image")
    visible = (H - fy) / fh if fh else 1
    if visible < 0.55:
        add(WARN, f"Only {visible:.0%} of the device is visible — most of the screen is cut off at the bottom")

    for name, blk, key, present in (("Title", t, "title_color", has_title), ("Subtitle", s, "subtitle_color", has_sub)):
        if not present:
            continue
        mid = (blk["top"] + blk["bottom"]) // 2
        ratio = contrast(_rgb(kw[key]), _bg_at(kw, mid))
        if ratio < 3:
            add(ERROR, f"{name} contrast {ratio:.1f}:1 on its background — hard to read (aim for 4.5:1)")
        elif ratio < 4.5:
            add(WARN, f"{name} contrast {ratio:.1f}:1 — below 4.5:1")
    return out


def check_plan(plan, devices):
    """devices: [(name, platform, device_dict, in_plan)] for the plan's selected locale."""
    from app.plan import compose_kwargs

    issues = []
    if not plan.screenshots:
        issues.append(Issue(ERROR, "No screenshots in the plan"))
    if plan.locales:
        names = {s.get("filename") for s in plan.screenshots}
        for loc, entries in plan.locales.items():
            texts = {e.get("filename") for e in entries}
            for f in sorted(texts - names, key=str):
                issues.append(Issue(WARN, f"{loc}: text for \"{f}\" matches no screenshot"))
            for f in sorted(names - texts, key=str):
                issues.append(Issue(WARN, f"{loc}: no title/subtitle for \"{f}\""))

    shots = plan.shots()
    font_checked = set()
    for name, platform, device, in_plan in devices:
        cfgs = [plan.cfg(device, shot) for shot in shots]
        base = plan.cfg(device, {})
        for iss in _style_issues(base):
            iss.device = name
            issues.append(iss)
        font = base.get("font", "Roboto")
        if font not in font_checked:
            font_checked.add(font)
            issues += _font_issues(base)
        kws = []
        for i, cfg in enumerate(cfgs):
            try:
                kws.append(compose_kwargs(cfg, None))
            except Exception as e:
                issues.append(Issue(ERROR, f"Bad config: {e}", name, i))
        if not kws:
            continue
        frame = DEVICE_FRAMES.get(kws[0]["frame_name"], {})
        issues += _store_issues(platform, name, kws[0]["canvas_w"], kws[0]["canvas_h"], len(kws), frame)
        for i, kw in enumerate(kws):
            if any(not _HEX.match(str(kw[k])) for k in ("bg_color1", "bg_color2", "title_color", "subtitle_color")):
                continue   # already reported; contrast can't be computed
            issues += check_image(kw, name, i)
    return issues
