# App Listing Studio
### Android Play Store Listing Asset Generator

Turn raw device screenshots into polished Google Play listing images — with device frames, gradient backgrounds, and custom text. One click to capture, one click to export.

> **Platform support:** Android only. iOS is not currently supported.

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
