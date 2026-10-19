# App Listing Studio
### Play Store & App Store Listing Asset Generator

Turn raw device screenshots into polished Google Play and App Store listing images — with device frames, gradient backgrounds, and custom text. One click to capture, one click to export.

> **Platform support:** captures come from Android devices/emulators via ADB. App Store images are made from the same captures: pick an iOS frame (**iPhone 16 Pro Max**, **iPad Pro 13**) and the Android status and nav bars are cropped off and replaced with an iOS status bar (9:41, signal, wifi, battery), Dynamic Island and home indicator. Bar heights are read from the device on capture; for imported files they are estimated and can be adjusted under **Crop Android**. Works best when the app's UI looks the same on both platforms (e.g. Capacitor/Flutter/React Native) — Android-only UI such as Material back arrows can still get an App Store rejection.

---

## Store Preview (main view)

**My listings** (left column) holds your app repos and loose plan files — add with **+** (repo folder, plan JSON, or *Scan folder for repos…* to add every subfolder with `fastlane/` or a plan), remove with **✕** (files are untouched). Saved in `~/.app_listing_studio/config.json`.

Each repo can be previewed from:
- **Store files (fastlane)** — the images already in fastlane: `metadata/android/<locale>/images/*Screenshots/` for Play, `screenshots/<locale>/` for the App Store (grouped by device from `APP_IPHONE_67`-style names or pixel size). Listing text and icon come from the fastlane metadata `.txt` files.
- **Plan: …** — any plan JSON found in the repo, rendered from raw captures.

Open a plan JSON and see it as a Google Play or App Store listing page: icon, name, rating row, install button, the screenshot carousel at store size, and the description. Toggle store, device (phone / tablet / iPhone / iPad) and light/dark.

The plan file, icon and raw screenshots are watched — edit the JSON in your editor, save, and the preview re-renders. Invalid JSON mid-edit keeps the last good preview and shows the error in the toolbar. The last opened plan reopens on start.

Plan keys used by the preview (see `example_plan.json`):

| Key | Meaning |
|---|---|
| `app.name`, `developer`, `icon`, `rating`, `downloads`, `age`, `short_description`, `description` | Listing page text; `icon` is relative to the plan |
| `source_dir` | Folder with the raw screenshots, relative to the plan (devices can override it, e.g. tablet captures) |
| `screenshots[].source` | Raw screenshot file; defaults to `filename` |
| `devices[].platform` | `android` / `ios`; normally inferred from `frame` |
| `android_bars`, `ios_native` | iOS conversion: `[top, bottom]` px to crop, or skip it for real iOS shots |

Screenshot Studio, Copy Preferences, Config Viewer and Saved Apps are under **Deprecated tools** in the sidebar until capture moves into the plan workflow.

---

## Requirements

- Python 3.11+
- ADB (Android Platform Tools)
- A USB-connected Android device with USB Debugging enabled

---

## Setup — Windows

### 1. Install Python
Download Python 3.11+ from https://python.org  
Check **"Add Python to PATH"** during install.

### 2. Install ADB (Android Platform Tools)
Download from: https://developer.android.com/tools/releases/platform-tools  
Extract to a folder like `C:\platform-tools\`

Add to PATH:
- Search "Environment Variables" in Start
- Edit `Path` → Add `C:\platform-tools\`

Test: `adb version`

### 3. Install dependencies
```
pip install -r requirements.txt
```

### 4. Run
```
python main.py
```
Or double-click `run.bat`

---

## Setup — Linux

### 1. Install Python
Most distros ship Python 3.11+. Check with `python3 --version`.

### 2. Install ADB
```bash
sudo apt install adb          # Debian/Ubuntu
sudo pacman -S android-tools  # Arch
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

PyQt6 may also need Qt6 system libraries:
```bash
sudo apt install python3-pyqt6   # if pip install fails
```

### 4. Run
```bash
python3 main.py
```

---

## iOS Simulator (macOS)

On a Mac with Xcode installed, booted iOS Simulators show up in the device list next to ADB devices (🍎). Capturing from one sets Apple's marketing status bar (9:41, full signal and battery) via `xcrun simctl status_bar` and takes a native screenshot — no Android bar swap. **Clean / Restore Status Bar** works on simulators too. Simulator captures are saved as `screenshots/capture_ios_*.png`; for other imported iOS screenshots tick **Native iOS** in the Crop Android row.

Boot a simulator first: `open -a Simulator` (or `xcrun simctl boot "iPhone 16 Pro Max"`), then **⟳ Scan**.

---

## Enable USB Debugging on your device

1. Go to **Settings → About Phone**
2. Tap **Build Number** 7 times
3. Go back → **Developer Options → USB Debugging: ON**
4. Connect phone via USB and accept the "Allow USB debugging" prompt

---

## Usage

1. **Scan** — click "⟳ Scan" to detect your connected device
2. **Capture** — click "📸 Capture Screenshot from Device"
3. **Customize** — choose device frame, background colors, title & subtitle
4. **Export** — click "⬇ Export PNG" → saves a 1080×1920 store-ready PNG

### Tips
- Import an existing screenshot from file instead of capturing
- Use **presets** for quick background colors
- Preview updates live as you change settings
- Batch export with a JSON plan file for multiple device sizes at once
- iOS devices in a plan can set `output_dir` (e.g. `fastlane/screenshots`) and `filename_prefix` (e.g. `iphone_`, `ipad_`) so iPhone and iPad shots share fastlane's `en-US` folder — see `example_plan.json`

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "ADB not found" | Add platform-tools to PATH, restart terminal |
| "No devices found" | Enable USB debugging, try a different cable |
| Device shows as "unauthorized" | Accept the popup on your phone |
| Screenshot is black | Some apps block screencapture — try another app |

---

## Contributing

Pull requests welcome. Please open an issue first for larger changes.

## License

MIT
