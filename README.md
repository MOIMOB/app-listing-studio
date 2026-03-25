# App Listing Studio
### iOS & Android Store Listing Asset Generator for Windows

Turn raw device screenshots into polished App Store and Play Store listing images — with device frames, gradient backgrounds, and custom text. One click to capture, one click to export.

---

## Setup (Windows)

### 1. Install Python
Download Python 3.11+ from https://python.org  
✅ Check **"Add Python to PATH"** during install.

### 2. Install ADB (Android Platform Tools)
Download from: https://developer.android.com/tools/releases/platform-tools  
Extract the zip to a folder like `C:\platform-tools\`  

Add it to PATH:
- Search "Environment Variables" in Start
- Edit `Path` → Add `C:\platform-tools\`

Test in terminal: `adb version`

### 3. Install app dependencies
Open a terminal in this folder and run:
```
pip install -r requirements.txt
```

### 4. Enable USB Debugging on your phone
- Go to **Settings → About Phone**
- Tap **Build Number** 7 times
- Go back → **Developer Options → USB Debugging: ON**
- Connect phone via USB
- Accept the "Allow USB debugging" prompt on your phone

### 5. Run the app
```
python main.py
```

Or double-click `run.bat`

---

## Usage

1. **Scan** — click "⟳ Scan" to detect your connected device
2. **Capture** — click "📸 Capture Screenshot from Device"
3. **Customize** — choose device frame, background colors, title & subtitle
4. **Export** — click "⬇ Export PNG" → saves a 1080×1920 store listing ready PNG

### Tips
- You can also **import** an existing screenshot from file
- Use **presets** for quick background colors
- The preview updates live as you change settings
- Export produces full 1080×1920px at full quality

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "ADB not found" | Add platform-tools to PATH, restart terminal |
| "No devices found" | Enable USB debugging, try a different cable |
| Device shows as "unauthorized" | Accept the popup on your phone |
| Screenshot is black | Some apps block screencapture — try another app |
