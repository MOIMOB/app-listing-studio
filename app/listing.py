"""
Listings — what the Store Preview shows.

A *listing entry* is a path saved under "My listings": an app repo folder or a plan JSON.
A repo can offer several *sources*:
  • "Store files"  — the images already in fastlane (what is, or will be, uploaded)
  • each plan JSON found in the repo — rendered from the raw captures

Every source answers the same questions: which locales, which devices per store,
which screenshots per device, and the listing text for each store.

fastlane layouts understood:
  Android  fastlane/metadata/android/<locale>/{title,short_description,full_description}.txt
           fastlane/metadata/android/<locale>/images/{icon.png, phoneScreenshots/, ...}
  iOS      fastlane/metadata[/ios]/<locale>/{name,subtitle,description}.txt
           fastlane/screenshots/<locale>/*.png   (grouped by device: APP_IPHONE_67 tokens or pixel size)
"""

import os
import re

from PIL import Image

from app.plan import load_plan, compose_kwargs

_LOCALE_RE = re.compile(r"^(?!android$|ios$)[a-z]{2,3}(-[A-Za-z0-9]+)*$")
_IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")

ANDROID_DIRS = [
    ("phoneScreenshots", "Phone"),
    ("sevenInchScreenshots", "7\" Tablet"),
    ("tenInchScreenshots", "10\" Tablet"),
    ("tvScreenshots", "TV"),
    ("wearScreenshots", "Wear"),
]

# fastlane snapshot device tokens → display name
IOS_TOKENS = {
    "APP_IPHONE_69": "iPhone 6.9\"", "APP_IPHONE_67": "iPhone 6.7\"", "APP_IPHONE_65": "iPhone 6.5\"",
    "APP_IPHONE_61": "iPhone 6.1\"", "APP_IPHONE_58": "iPhone 5.8\"", "APP_IPHONE_55": "iPhone 5.5\"",
    "APP_IPAD_PRO_129": "iPad Pro 12.9\"", "APP_IPAD_PRO_3GEN_129": "iPad Pro 12.9\" (3rd gen+)",
    "APP_IPAD_PRO_13": "iPad 13\"", "APP_IPAD_PRO_11": "iPad Pro 11\"", "APP_IPAD_105": "iPad 10.5\"",
}
# App Store pixel sizes (portrait) → display name, for screenshots without a token in the name
IOS_SIZES = {
    (1320, 2868): "iPhone 6.9\"", (1290, 2796): "iPhone 6.7\"", (1284, 2778): "iPhone 6.5\"",
    (1242, 2688): "iPhone 6.5\"", (1179, 2556): "iPhone 6.1\"", (1242, 2208): "iPhone 5.5\"",
    (2064, 2752): "iPad 13\"", (2048, 2732): "iPad Pro 12.9\"", (1668, 2388): "iPad Pro 11\"",
}

_ANDROID_TEXT = {"title.txt": "name", "short_description.txt": "short_description",
                 "full_description.txt": "description"}
_IOS_TEXT = {"name.txt": "name", "subtitle.txt": "short_description", "description.txt": "description"}


def _natural(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def _images_in(folder):
    if not os.path.isdir(folder):
        return []
    return sorted((os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(_IMG_EXT)),
                  key=lambda p: _natural(os.path.basename(p)))


def _subdirs(folder):
    return sorted(d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))) if os.path.isdir(folder) else []


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def find_fastlane(start_dir, levels=4):
    """The fastlane/ folder in start_dir or one of its parents."""
    d = start_dir
    for _ in range(levels):
        cand = os.path.join(d, "fastlane")
        if os.path.isdir(os.path.join(cand, "metadata")) or os.path.isdir(os.path.join(cand, "screenshots")):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return ""


def _ios_meta_dir(fastlane, locale):
    # Apple uses plain language codes for some locales ("sv" where Play has "sv-SE")
    names = [locale, locale.split("-")[0]] if locale else []
    for cand in [os.path.join(fastlane, "metadata", sub, n) for n in names for sub in ("ios", "")]:
        if os.path.isfile(os.path.join(cand, "name.txt")) or os.path.isfile(os.path.join(cand, "description.txt")):
            return cand
    return ""


def fastlane_app_info(fastlane, platform, locale):
    """Listing text + icon from fastlane metadata for one store and locale."""
    info = {}
    if not fastlane:
        return info
    android_dir = os.path.join(fastlane, "metadata", "android", locale)
    if platform == "android":
        meta, fields = android_dir, _ANDROID_TEXT
    else:
        meta, fields = _ios_meta_dir(fastlane, locale), _IOS_TEXT
    for fname, key in fields.items():
        text = _read(os.path.join(meta, fname)) if meta else ""
        if text:
            info[key] = text
    # iOS keeps the icon in the Xcode project, so both stores borrow the Play Store icon
    icon = os.path.join(android_dir, "images", "icon.png")
    if os.path.isfile(icon):
        info["icon"] = icon
    return info


# ─── Sources ──────────────────────────────────────────────────────────────────

class StoreFilesSource:
    """Screenshots already in fastlane, shown as-is."""

    label = "Store files"

    def __init__(self, fastlane):
        self.fastlane = fastlane
        self.name = os.path.basename(os.path.dirname(fastlane))
        android = [d for d in _subdirs(os.path.join(fastlane, "metadata", "android")) if _LOCALE_RE.match(d)]
        ios_shots = [d for d in _subdirs(os.path.join(fastlane, "screenshots")) if _LOCALE_RE.match(d)]
        ios_meta = [d for d in _subdirs(os.path.join(fastlane, "metadata", "ios")) + _subdirs(os.path.join(fastlane, "metadata"))
                    if _LOCALE_RE.match(d)]
        found = set(android) | set(ios_shots) | set(ios_meta)
        # "sv" next to "sv-SE" is the same language in Apple's naming; list it once
        self.locales = sorted(l for l in found if not any(o.startswith(l + "-") for o in found))
        self.locale = "en-US" if "en-US" in self.locales else (self.locales[0] if self.locales else "")

    def app_info(self, platform):
        info = fastlane_app_info(self.fastlane, platform, self.locale)
        info.setdefault("name", self.name)
        return info

    def _ios_groups(self):
        groups = {}
        for path in _images_in(os.path.join(self.fastlane, "screenshots", self.locale)):
            stem = os.path.splitext(os.path.basename(path))[0]
            m = re.search(r"(APP_[A-Z0-9_]+?)_\d+$", stem)
            if m:
                label = IOS_TOKENS.get(m.group(1), m.group(1))
            else:
                try:
                    w, h = Image.open(path).size
                except Exception:
                    continue
                label = IOS_SIZES.get((min(w, h), max(w, h)), f"{w}×{h}")
            groups.setdefault(label, []).append(path)
        # iPhones before iPads, as App Store Connect lists them
        return dict(sorted(groups.items(), key=lambda kv: (not kv[0].startswith("iPhone"), kv[0])))

    def devices(self, platform):
        if platform == "android":
            base = os.path.join(self.fastlane, "metadata", "android", self.locale, "images")
            return [label for d, label in ANDROID_DIRS if _images_in(os.path.join(base, d))]
        return list(self._ios_groups())

    def shots(self, platform, device):
        """[(title, path, None)] — None = no compose kwargs, show the file as-is."""
        if platform == "android":
            folder = dict((label, d) for d, label in ANDROID_DIRS)[device]
            paths = _images_in(os.path.join(self.fastlane, "metadata", "android", self.locale, "images", folder))
        else:
            paths = self._ios_groups().get(device, [])
        return [(os.path.basename(p), p, None) for p in paths]

    def watch_paths(self):
        paths = []
        a = os.path.join(self.fastlane, "metadata", "android", self.locale)
        paths += [os.path.join(a, "images", d) for d, _ in ANDROID_DIRS] + [a]
        paths += [os.path.join(self.fastlane, "screenshots", self.locale)]
        ios = _ios_meta_dir(self.fastlane, self.locale)
        if ios:
            paths.append(ios)
        return [p for p in paths if os.path.exists(p)]

    def missing(self, platform, device):
        return []


class PlanSource:
    """A plan JSON, rendered from raw captures."""

    def __init__(self, path, root=""):
        self.path = path
        self.label = os.path.relpath(path, root) if root else os.path.basename(path)
        self.locale = ""
        self.reload()

    def reload(self):
        """Raises on invalid JSON — the caller keeps showing the last good state."""
        self.plan = load_plan(self.path, self.locale)
        self.locale = self.plan.locale
        self.locales = list(self.plan.locales)
        self.fastlane = find_fastlane(self.plan.dir)

    def app_info(self, platform):
        info = fastlane_app_info(self.fastlane, platform, self.locale or "en-US")
        info.update(self.plan.app_info(platform))
        info.setdefault("name", os.path.splitext(os.path.basename(self.path))[0].replace("_", " ").replace("-", " ").title())
        return info

    def _device_map(self, platform):
        plan = self.plan
        return {plan.device_name(i): d for i, d in enumerate(plan.devices) if plan.platform(d) == platform}

    def devices(self, platform):
        return list(self._device_map(platform))

    def shots(self, platform, device):
        """[(title, raw_path, compose_kwargs_without_bytes)]"""
        d = self._device_map(platform)[device]
        out = []
        for shot in self.plan.shots():
            cfg = self.plan.cfg(d, shot)
            out.append((cfg.get("title") or cfg.get("filename", ""), self.plan.source_path(cfg),
                        compose_kwargs(cfg, None)))
        return out

    def missing(self, platform, device):
        return [p for _, p, _ in self.shots(platform, device) if not (p and os.path.exists(p))]

    def watch_paths(self):
        paths = {self.path}
        for platform in ("android", "ios"):
            for dev in self.devices(platform):
                for _, p, _ in self.shots(platform, dev):
                    if p:
                        paths.add(os.path.dirname(p))   # catches new/renamed captures
                        paths.add(p)
            icon = self.app_info(platform).get("icon")
            if icon:
                paths.add(icon)
        return sorted(p for p in paths if os.path.exists(p))


# ─── Entries ──────────────────────────────────────────────────────────────────

_SKIP_DIRS = {"node_modules", ".git", "build", "dist", "android", "ios", "www", ".gradle", "Pods", "venv", ".venv"}


def find_plans(root, max_depth=4):
    """Plan JSONs under root: objects with a "screenshots" list plus devices/defaults."""
    import json
    found = []
    root_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        if dirpath.count(os.sep) - root_depth >= max_depth:
            dirnames[:] = []
        for f in filenames:
            if not f.endswith(".json") or f in ("package.json", "package-lock.json", "tsconfig.json"):
                continue
            p = os.path.join(dirpath, f)
            try:
                if os.path.getsize(p) > 512_000:
                    continue
                with open(p, encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                continue
            if isinstance(data, dict) and isinstance(data.get("screenshots"), list) and \
                    ("devices" in data or "defaults" in data):
                found.append(p)
    return sorted(found)


class Entry:
    """One row in "My listings": a repo folder or a single plan file."""

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.is_file = os.path.isfile(self.path)
        self.root = os.path.dirname(self.path) if self.is_file else self.path
        self.name = (os.path.splitext(os.path.basename(self.path))[0] if self.is_file
                     else os.path.basename(self.path))

    def exists(self):
        return os.path.exists(self.path)

    def sources(self):
        """Store files first (when the repo has fastlane screenshots), then plans. Scanned once per Entry."""
        if getattr(self, "_sources", None) is None:
            self._sources = self._scan()
        return self._sources

    def _scan(self):
        out = []
        if self.is_file:
            out.append(("plan", self.path))
            return out
        fl = os.path.join(self.root, "fastlane")
        if os.path.isdir(fl):
            out.append(("store", fl))
        out += [("plan", p) for p in find_plans(self.root)]
        return out

    def open_source(self, kind, path):
        return StoreFilesSource(path) if kind == "store" else PlanSource(path, "" if self.is_file else self.root)

    def summary(self):
        """Short subtitle for the list row."""
        kinds = [k for k, _ in self.sources()]
        bits = []
        if "store" in kinds:
            bits.append("fastlane")
        n = kinds.count("plan")
        if n:
            bits.append(f"{n} plan" + ("s" if n > 1 else ""))
        return " · ".join(bits) or "nothing found"


def load_preview_image(path, kwargs, render_w):
    """PIL image for one thumbnail: the file itself, or a plan render scaled to render_w."""
    from main import compose_image
    if kwargs is None:
        img = Image.open(path).convert("RGB")
        if img.width > render_w:
            img = img.resize((render_w, round(img.height * render_w / img.width)), Image.LANCZOS)
        return img
    data = None
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
    scale = render_w / kwargs["canvas_w"]
    kw = {**kwargs, "screenshot_bytes": data,
          "canvas_w": render_w, "canvas_h": round(kwargs["canvas_h"] * scale),
          "phone_offset_y": int(kwargs["phone_offset_y"] * scale)}
    return compose_image(**kw)


def aspect_of(shots):
    """Width/height of the first screenshot (file size or plan canvas)."""
    for _, path, kwargs in shots:
        if kwargs is not None:
            return kwargs["canvas_w"] / kwargs["canvas_h"]
        try:
            w, h = Image.open(path).size
            return w / h
        except Exception:
            continue
    return 9 / 16
