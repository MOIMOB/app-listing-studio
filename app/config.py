"""
AppConfig — lightweight JSON config persisted to ~/.app_listing_studio/config.json

Schema:
{
  "apps": [{"name": "My App", "package": "com.example.myapp"}, ...],
  "last_copy_package": "com.example.myapp"
}
"""

import json
from pathlib import Path

_CONFIG_DIR  = Path.home() / ".app_listing_studio"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def _load() -> dict:
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"apps": [], "last_copy_package": ""}


def _save(data: dict):
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class AppConfig:
    # ── Saved apps ────────────────────────────────────────────────────────────

    @staticmethod
    def get_apps() -> list[dict]:
        """Return list of {"name": str, "package": str}."""
        return _load().get("apps", [])

    @staticmethod
    def add_app(name: str, package: str):
        """Add or update an app entry (keyed by package)."""
        data = _load()
        data["apps"] = [a for a in data.get("apps", []) if a["package"] != package]
        data["apps"].append({"name": name.strip(), "package": package.strip()})
        _save(data)

    @staticmethod
    def remove_app(package: str):
        data = _load()
        data["apps"] = [a for a in data.get("apps", []) if a["package"] != package]
        _save(data)

    # ── Last used package ─────────────────────────────────────────────────────

    @staticmethod
    def get_last_package() -> str:
        return _load().get("last_copy_package", "")

    @staticmethod
    def set_last_package(package: str):
        data = _load()
        data["last_copy_package"] = package.strip()
        _save(data)
