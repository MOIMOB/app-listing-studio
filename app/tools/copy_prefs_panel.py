"""
CopyPrefsPanel — SharedPreferences copy tool.

Two usage modes:
  • Standalone tool page  → CopyPrefsPanel(compact=False)
      Has its own ADB scan button; self-contained.
  • Embedded in Screenshot Studio → CopyPrefsPanel(compact=True)
      Call set_devices(devices) to sync device list from the parent scanner.
      Scan button is hidden to avoid redundancy.

Package selection:
  • Editable combo — shows saved apps, also accepts free-text package names.
  • 💾 button saves the current package to the app list (prompts for a display name).
  • ⚙ button opens a Manage dialog to rename/delete saved apps.
  • Last-used package is persisted to config and restored on next launch.
"""

import os
import subprocess
import tempfile
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QProgressBar, QGroupBox, QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from app.config import AppConfig


class CopyPrefsPanel(QWidget):
    logged = pyqtSignal(str)

    def __init__(self, compact: bool = False, parent=None):
        super().__init__(parent)
        self._compact = compact
        self._devices = []
        self._worker  = None
        self._build()
        self._load_saved_apps()
        self._restore_last_package()

    # ── Public API ────────────────────────────────────────────────────────────

    def set_devices(self, devices: list):
        """Push device list from an external scanner (embedded mode)."""
        self._devices = devices
        self._populate_device_combos(devices)

    # ── Construction ──────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0 if self._compact else 24, 0 if self._compact else 24,
                                0 if self._compact else 24, 0 if self._compact else 24)
        root.setSpacing(14)

        if not self._compact:
            self._build_header(root)

        if not self._compact:
            scan_row = QHBoxLayout()
            self._scan_btn = QPushButton("⟳  Scan Devices")
            self._scan_btn.clicked.connect(self._scan_devices)
            scan_row.addWidget(self._scan_btn)
            scan_row.addStretch()
            root.addLayout(scan_row)

            self._scan_status = QLabel("Click Scan to detect ADB devices.")
            self._scan_status.setStyleSheet("color:#667; font-size:11px;")
            root.addWidget(self._scan_status)

        grp = QGroupBox("COPY SHARED PREFERENCES" if not self._compact else "")
        grp.setFlat(self._compact)
        form = QVBoxLayout(grp)
        form.setSpacing(10)

        # ── Package row ───────────────────────────────────────────────────────
        pkg_row = QHBoxLayout()
        pkg_row.setSpacing(4)
        pkg_lbl = QLabel("Package:")
        pkg_lbl.setFixedWidth(80)
        pkg_lbl.setStyleSheet("color:#8890aa; font-size:12px;")

        self._pkg_combo = QComboBox()
        self._pkg_combo.setEditable(True)
        self._pkg_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._pkg_combo.lineEdit().setPlaceholderText("com.example.myapp")
        self._pkg_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        pkg_row.addWidget(pkg_lbl)
        pkg_row.addWidget(self._pkg_combo, 1)
        form.addLayout(pkg_row)

        # ── Device rows ───────────────────────────────────────────────────────
        from_row = QHBoxLayout()
        from_lbl = QLabel("From:")
        from_lbl.setFixedWidth(80)
        from_lbl.setStyleSheet("color:#8890aa; font-size:12px;")
        self._from_combo = QComboBox()
        from_row.addWidget(from_lbl)
        from_row.addWidget(self._from_combo, 1)
        form.addLayout(from_row)

        to_row = QHBoxLayout()
        to_lbl = QLabel("To:")
        to_lbl.setFixedWidth(80)
        to_lbl.setStyleSheet("color:#8890aa; font-size:12px;")
        self._to_combo = QComboBox()
        to_row.addWidget(to_lbl)
        to_row.addWidget(self._to_combo, 1)
        form.addLayout(to_row)

        # ── Copy button ───────────────────────────────────────────────────────
        self._copy_btn = QPushButton("🔁  Copy Preferences")
        self._copy_btn.setObjectName("primary")
        self._copy_btn.clicked.connect(self._do_copy)
        form.addWidget(self._copy_btn)

        note = QLabel("Requires a debuggable build or rooted device.")
        note.setStyleSheet("color:#445566; font-size:10px; font-style:italic;")
        form.addWidget(note)

        root.addWidget(grp)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#6a9a6a; font-size:11px;")
        self._status_lbl.setWordWrap(True)
        root.addWidget(self._status_lbl)

        root.addStretch()

    def _build_header(self, root: QVBoxLayout):
        title = QLabel("Copy Preferences")
        title.setStyleSheet("font-size:22px; font-weight:bold; color:#eef;")
        root.addWidget(title)

        desc = QLabel(
            "Transfer an app's SharedPreferences from one ADB device to another.\n"
            "Useful for seeding emulator state from a physical device."
        )
        desc.setStyleSheet("color:#778; font-size:13px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#1e1e38;")
        root.addWidget(sep)

    # ── App list helpers ──────────────────────────────────────────────────────

    def _load_saved_apps(self):
        """Populate the package combo from config, preserving the current selection."""
        current_pkg = self._current_package()   # raw package, not display text
        self._pkg_combo.blockSignals(True)
        self._pkg_combo.clear()
        for app in AppConfig.get_apps():
            display = f"{app['name']}  —  {app['package']}"
            self._pkg_combo.addItem(display, userData=app["package"])
        self._pkg_combo.blockSignals(False)
        if current_pkg:
            self._set_package(current_pkg)

    def showEvent(self, event):
        """Refresh the app list whenever this panel is navigated to."""
        super().showEvent(event)
        self._load_saved_apps()

    def _restore_last_package(self):
        last = AppConfig.get_last_package()
        if last:
            self._set_package(last)

    def _set_package(self, package: str):
        """Select a saved-app item whose data matches `package`, else free-type it."""
        for i in range(self._pkg_combo.count()):
            if self._pkg_combo.itemData(i) == package:
                self._pkg_combo.setCurrentIndex(i)
                return
        self._pkg_combo.setCurrentText(package)

    def _current_package(self) -> str:
        """Return the effective package — item data if a saved app is selected, else raw text."""
        data = self._pkg_combo.currentData()
        if data:
            return data
        return self._pkg_combo.currentText().strip()

    # ── Device scanning (standalone) ──────────────────────────────────────────

    def _scan_devices(self):
        from main import ADBWorker
        if hasattr(self, "_scan_btn"):
            self._scan_btn.setEnabled(False)
        self._set_status("Scanning for ADB devices…")
        worker = ADBWorker("list")
        worker.devices_found.connect(self._on_scan_done)
        worker.error.connect(lambda msg: self._set_status(f"⚠ {msg}"))
        worker.log.connect(self._set_status)
        self._worker = worker
        worker.start()

    def _on_scan_done(self, devices):
        self._devices = devices
        self._populate_device_combos(devices)
        if hasattr(self, "_scan_btn"):
            self._scan_btn.setEnabled(True)
        n = len(devices)
        msg = f"Found {n} device(s)." if n else "No devices found."
        if hasattr(self, "_scan_status"):
            self._scan_status.setText(msg)
        self._set_status(msg)

    def _populate_device_combos(self, devices: list):
        self._from_combo.clear()
        self._to_combo.clear()
        if devices:
            for d in devices:
                if d["is_emulator"]:
                    label = f"🖥  {d['avd_name'] or d['model']}  ({d['serial']})"
                else:
                    label = f"📱  {d['model']}  ({d['serial']})"
                self._from_combo.addItem(label, d["serial"])
                self._to_combo.addItem(label, d["serial"])
            if len(devices) > 1:
                self._to_combo.setCurrentIndex(1)
        else:
            self._from_combo.addItem("No devices found")
            self._to_combo.addItem("No devices found")

    # ── Copy logic ────────────────────────────────────────────────────────────

    def _do_copy(self):
        pkg = self._current_package()
        src = self._from_combo.currentData()
        dst = self._to_combo.currentData()

        if not pkg:
            QMessageBox.warning(self, "Missing Package", "Enter or select a package name.")
            return
        if not src or not dst:
            QMessageBox.warning(self, "Missing Device", "Select source and destination devices.")
            return
        if src == dst:
            QMessageBox.warning(self, "Same Device", "Source and destination must be different.")
            return

        self._copy_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._set_status(f"Copying prefs {src} → {dst}…")

        def _done(ok: bool, msg: str):
            self._copy_btn.setEnabled(True)
            self._progress.setVisible(False)
            self._set_status(("✓ " if ok else "✗ ") + msg.splitlines()[0])
            if ok:
                AppConfig.set_last_package(pkg)
                QTimer.singleShot(50, lambda: QMessageBox.information(self, "Done", msg))
            else:
                QTimer.singleShot(50, lambda: QMessageBox.critical(self, "Copy Failed", msg))

        def _run():
            import shutil
            tmp = tempfile.mkdtemp(prefix="adb_prefs_")
            try:
                tar_path = os.path.join(tmp, "prefs.tar")

                QTimer.singleShot(0, lambda: self._set_status("Pulling shared_prefs from source…"))
                subprocess.run(
                    ["adb", "-s", src, "exec-out",
                     f"run-as {pkg} tar cf - -C /data/data/{pkg} shared_prefs"],
                    capture_output=False,
                    stdout=open(tar_path, "wb"),
                    timeout=60,
                )
                if os.path.getsize(tar_path) < 10:
                    raise RuntimeError(
                        "Pull failed — got empty tar.\n\n"
                        "Make sure:\n"
                        "• The app is installed on the source device\n"
                        "• The build is debuggable (not a release build)"
                    )

                sdcard_tar = f"/sdcard/prefs_tmp_{pkg}.tar"
                QTimer.singleShot(0, lambda: self._set_status("Pushing to destination…"))
                result = subprocess.run(
                    ["adb", "-s", dst, "push", tar_path, sdcard_tar],
                    capture_output=True, timeout=30,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"Push failed:\n{result.stderr.decode(errors='replace').strip()}"
                    )

                QTimer.singleShot(0, lambda: self._set_status("Extracting on destination…"))
                result = subprocess.run(
                    ["adb", "-s", dst, "shell",
                     f"run-as {pkg} tar xf {sdcard_tar} -C /data/data/{pkg}/ && rm {sdcard_tar}"],
                    capture_output=True, timeout=30,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"Extract failed:\n{result.stderr.decode(errors='replace').strip()}"
                    )

                msg = (
                    f"Preferences copied successfully.\n\n"
                    f"From: {src}\nTo:   {dst}\n\n"
                    f"Restart the app on {dst} to apply."
                )
                QTimer.singleShot(0, lambda: _done(True, msg))
            except Exception as exc:
                QTimer.singleShot(0, lambda: _done(False, str(exc)))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

        threading.Thread(target=_run, daemon=True).start()

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)
        self.logged.emit(msg)
