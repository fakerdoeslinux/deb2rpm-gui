#!/usr/bin/env python3
"""
deb2rpm-gui: A native Fedora GUI and CLI utility to convert Debian (.deb)
packages into RPM (.rpm) packages using alien and fakeroot.

Author: FAKERH0G
License: MIT
"""

import sys
import os
import shutil
import subprocess
import argparse
import tempfile
import time
from pathlib import Path

# Tool dependencies
REQUIRED_TOOLS = {
    "alien": "alien",
    "rpmbuild": "rpm-build",
    "fakeroot": "fakeroot"
}

def check_missing_tools():
    missing = []
    for tool, pkg in REQUIRED_TOOLS.items():
        if not shutil.which(tool):
            missing.append((tool, pkg))
    return missing

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def run_cli(args):
    print("=" * 60)
    print("  deb2rpm - Debian to RPM Package Converter for Fedora")
    print("=" * 60)

    missing = check_missing_tools()
    if missing:
        print("\n[!] Missing required dependencies:")
        for tool, pkg in missing:
            print(f"    - {tool} (Fedora package: {pkg})")
        print("\nPlease install missing packages with:")
        print("    sudo dnf install " + " ".join(pkg for _, pkg in missing))
        sys.exit(1)

    input_files = []
    for f in args.files:
        p = Path(f).resolve()
        if not p.is_file() or not p.name.endswith(".deb"):
            print(f"[ERROR] '{f}' is not a valid Debian package (.deb).")
            sys.exit(1)
        input_files.append(p)

    if not input_files:
        print("[ERROR] No input .deb files provided.")
        sys.exit(1)

    out_dir = Path(args.output).resolve() if args.output else None
    success_count = 0
    generated_rpms = []

    for deb in input_files:
        target_dir = out_dir if out_dir else deb.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n[*] Processing: {deb.name}")
        print(f"    Source:      {deb}")
        print(f"    Destination: {target_dir}")

        existing_rpms = {r.name: r.stat().st_mtime for r in target_dir.glob("*.rpm")}

        cmd = []
        if shutil.which("fakeroot"):
            cmd.append("fakeroot")
        cmd.extend(["alien", "-r", "--verbose"])
        if args.keep_version:
            cmd.append("-k")
        if args.scripts:
            cmd.append("-c")
        if args.fixperms:
            cmd.append("--fixperms")
        cmd.append(str(deb))

        print(f"    Executing:   {' '.join(cmd)}")
        start_time = time.time()
        proc = subprocess.run(cmd, cwd=str(target_dir), capture_output=True, text=True)
        elapsed = time.time() - start_time

        if proc.stdout.strip():
            print(proc.stdout.strip())
        if proc.stderr.strip():
            print(proc.stderr.strip())

        if proc.returncode != 0:
            print(f"[FAIL] Conversion failed for {deb.name} (exit code {proc.returncode})")
        else:
            success_count += 1
            # Identify newly generated RPM
            new_rpm = None
            for line in proc.stdout.splitlines():
                if "generated" in line and ".rpm" in line:
                    parts = line.strip().split()
                    if parts:
                        rpm_candidate = target_dir / parts[0]
                        if rpm_candidate.exists():
                            new_rpm = rpm_candidate
                            break
            if not new_rpm:
                for r in target_dir.glob("*.rpm"):
                    if r.name not in existing_rpms or r.stat().st_mtime > existing_rpms[r.name]:
                        new_rpm = r
                        break

            if new_rpm:
                generated_rpms.append(new_rpm)
                print(f"[OK] Converted {deb.name} -> {new_rpm.name} in {elapsed:.2f}s")
            else:
                print(f"[OK] Converted {deb.name} in {elapsed:.2f}s")

    print("\n" + "=" * 60)
    print(f" Summary: {success_count}/{len(input_files)} packages successfully converted.")
    if generated_rpms:
        print(" Generated RPM packages:")
        for r in generated_rpms:
            print(f"   -> {r}")
        if args.install:
            print("\n[*] Installing converted packages with DNF...")
            rpm_args = [str(r) for r in generated_rpms]
            subprocess.run(["pkexec", "dnf", "install", "-y"] + rpm_args)
    print("=" * 60)


# GUI Implementation
try:
    from PyQt6 import QtCore, QtGui, QtWidgets
    from PyQt6.QtCore import Qt, QThread, pyqtSignal as Signal, QUrl
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QFileDialog, QCheckBox, QTextEdit,
        QProgressBar, QGroupBox, QListWidget, QListWidgetItem,
        QMessageBox, QFrame, QRadioButton, QButtonGroup, QLineEdit
    )
    from PyQt6.QtGui import (
        QIcon, QFont, QColor, QPalette, QDragEnterEvent, QDropEvent,
        QDesktopServices, QTextCursor
    )
    QT_AVAILABLE = True
    QT_LIB = "PyQt6"
except ImportError:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
        from PySide6.QtCore import Qt, QThread, Signal, QUrl
        from PySide6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QPushButton, QLabel, QFileDialog, QCheckBox, QTextEdit,
            QProgressBar, QGroupBox, QListWidget, QListWidgetItem,
            QMessageBox, QFrame, QRadioButton, QButtonGroup, QLineEdit
        )
        from PySide6.QtGui import (
            QIcon, QFont, QColor, QPalette, QDragEnterEvent, QDropEvent,
            QDesktopServices, QTextCursor
        )
        QT_AVAILABLE = True
        QT_LIB = "PySide6"
    except ImportError:
        QT_AVAILABLE = False
        QT_LIB = None

if QT_AVAILABLE:
    class ConversionWorker(QThread):
        log_signal = Signal(str, str) # text, tag ('info', 'error', 'cmd', 'success')
        progress_signal = Signal(int, int, str) # current, total, filename
        finished_signal = Signal(bool, list, str) # success, list of rpms, error message

        def __init__(self, items, options):
            super().__init__()
            self.items = items
            self.options = options
            self._is_cancelled = False
            self.current_process = None

        def cancel(self):
            self._is_cancelled = True
            if self.current_process and self.current_process.poll() is None:
                try:
                    self.current_process.terminate()
                except Exception:
                    pass

        def run(self):
            total = len(self.items)
            generated_rpms = []
            has_error = False

            for idx, deb_path in enumerate(self.items):
                if self._is_cancelled:
                    self.log_signal.emit("Conversion cancelled by user.", "error")
                    self.finished_signal.emit(False, generated_rpms, "Cancelled")
                    return

                deb = Path(deb_path)
                self.progress_signal.emit(idx, total, deb.name)
                self.log_signal.emit(f"==> Starting conversion of {deb.name}", "info")

                target_dir = Path(self.options["output_dir"]) if self.options["output_dir"] else deb.parent
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self.log_signal.emit(f"Failed to create target directory {target_dir}: {e}", "error")
                    has_error = True
                    continue

                existing_rpms = {r.name: r.stat().st_mtime for r in target_dir.glob("*.rpm")}

                cmd = []
                if self.options.get("use_fakeroot") and shutil.which("fakeroot"):
                    cmd.append("fakeroot")
                cmd.extend(["alien", "-r", "--verbose"])
                if self.options.get("keep_version", True):
                    cmd.append("-k")
                if self.options.get("scripts", True):
                    cmd.append("-c")
                if self.options.get("fixperms", False):
                    cmd.append("--fixperms")
                cmd.append(str(deb))

                self.log_signal.emit(f"$ {' '.join(cmd)}", "cmd")

                start_time = time.time()
                try:
                    self.current_process = subprocess.Popen(
                        cmd,
                        cwd=str(target_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )

                    deb_generated = []
                    for line in iter(self.current_process.stdout.readline, ''):
                        line_str = line.strip()
                        if line_str:
                            self.log_signal.emit(line_str, "info")
                            if "generated" in line_str and ".rpm" in line_str:
                                parts = line_str.split()
                                if parts:
                                    rpm_candidate = target_dir / parts[0]
                                    if rpm_candidate.exists() and rpm_candidate not in deb_generated:
                                        deb_generated.append(rpm_candidate)

                    self.current_process.stdout.close()
                    rc = self.current_process.wait()
                    elapsed = time.time() - start_time

                    if rc != 0:
                        self.log_signal.emit(f"Error: alien returned exit code {rc}", "error")
                        has_error = True
                    else:
                        # Fallback check if rpm candidate wasn't captured in stdout line
                        if not deb_generated:
                            for r in target_dir.glob("*.rpm"):
                                if r.name not in existing_rpms or r.stat().st_mtime > existing_rpms[r.name]:
                                    deb_generated.append(r)

                        generated_rpms.extend(deb_generated)
                        rpm_names = ", ".join(r.name for r in deb_generated) if deb_generated else "RPM"
                        self.log_signal.emit(f"✓ Converted {deb.name} -> {rpm_names} ({elapsed:.1f}s)", "success")

                except Exception as e:
                    self.log_signal.emit(f"Execution error: {e}", "error")
                    has_error = True

            self.progress_signal.emit(total, total, "Finished")
            self.finished_signal.emit(not has_error, generated_rpms, "" if not has_error else "Some packages encountered errors.")

    class DropListWidget(QListWidget):
        files_dropped = Signal(list)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setAcceptDrops(True)
            self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        def dragEnterEvent(self, event: QDragEnterEvent):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                event.ignore()

        def dragMoveEvent(self, event):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                event.ignore()

        def dropEvent(self, event: QDropEvent):
            files = []
            if event.mimeData().hasUrls():
                for url in event.mimeData().urls():
                    local_path = url.toLocalFile()
                    if local_path.endswith(".deb") and os.path.isfile(local_path):
                        files.append(local_path)
                if files:
                    self.files_dropped.emit(files)
                    event.acceptProposedAction()
                    return
            event.ignore()

    class Deb2RpmWindow(QMainWindow):
        def __init__(self, initial_files=None, initial_output=None):
            super().__init__()
            self.setWindowTitle("DEB to RPM Converter")
            self.resize(840, 700)
            self.setMinimumSize(720, 580)

            # Look for icon
            icon_candidates = [
                Path(__file__).parent / "deb2rpm.svg",
                Path(__file__).parent / "deb2rpm.png",
                Path.home() / ".local/share/icons/hicolor/scalable/apps/deb2rpm.svg",
                Path("/usr/share/icons/hicolor/scalable/apps/deb2rpm.svg")
            ]
            for icon_path in icon_candidates:
                if icon_path.exists():
                    self.setWindowIcon(QIcon(str(icon_path)))
                    break

            self.worker = None
            self.queued_files = []
            self.last_rpms = []
            self.init_ui(initial_output)

            # Add any initial files passed from CLI or context menu
            if initial_files:
                self.add_files(initial_files)

            self.check_dependencies_banner()

        def init_ui(self, initial_output=None):
            central_widget = QWidget(self)
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)
            main_layout.setContentsMargins(16, 16, 16, 16)
            main_layout.setSpacing(12)

            # Top Header Card
            header_frame = QFrame()
            header_frame.setObjectName("headerFrame")
            header_frame.setStyleSheet("""
                QFrame#headerFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #1e293b, stop:0.5 #1e3a5f, stop:1 #0f172a);
                    border-radius: 8px;
                    border: 1px solid #334155;
                    padding: 8px;
                }
            """)
            header_layout = QHBoxLayout(header_frame)
            header_layout.setContentsMargins(14, 10, 14, 10)

            title_box = QVBoxLayout()
            title_label = QLabel("DEB to RPM Converter")
            title_label.setStyleSheet("font-size: 19px; font-weight: 800; color: #ffffff; letter-spacing: 0.5px;")
            subtitle_label = QLabel("Convert Debian (.deb) packages into native RPMs for Fedora Linux")
            subtitle_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
            title_box.addWidget(title_label)
            title_box.addWidget(subtitle_label)
            header_layout.addLayout(title_box)

            header_layout.addStretch()

            self.status_badge = QLabel("Ready")
            self.status_badge.setStyleSheet("""
                background-color: #065f46;
                color: #34d399;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 12px;
                border-radius: 12px;
                border: 1px solid #059669;
            """)
            header_layout.addWidget(self.status_badge)
            main_layout.addWidget(header_frame)

            # Missing Dependencies Warning Banner (Hidden by default)
            self.dep_banner = QFrame()
            self.dep_banner.setStyleSheet("""
                QFrame {
                    background-color: #451a03;
                    border: 1px solid #b45309;
                    border-radius: 6px;
                    padding: 6px 12px;
                }
                QLabel { color: #fde68a; font-weight: 600; font-size: 12px; }
            """)
            dep_layout = QHBoxLayout(self.dep_banner)
            dep_layout.setContentsMargins(10, 6, 10, 6)
            self.dep_label = QLabel()
            dep_layout.addWidget(self.dep_label)
            dep_layout.addStretch()

            self.install_dep_btn = QPushButton("Install via DNF")
            self.install_dep_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d97706;
                    color: #000000;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 14px;
                }
                QPushButton:hover { background-color: #f59e0b; }
            """)
            self.install_dep_btn.clicked.connect(self.install_dependencies)
            dep_layout.addWidget(self.install_dep_btn)
            self.dep_banner.setVisible(False)
            main_layout.addWidget(self.dep_banner)

            # Files List Group
            files_group = QGroupBox("Packages to Convert")
            files_layout = QVBoxLayout(files_group)

            self.file_list = DropListWidget()
            self.file_list.files_dropped.connect(self.add_files)
            self.file_list.setStyleSheet("""
                QListWidget {
                    border: 2px dashed #475569;
                    border-radius: 6px;
                    background-color: #0f172a;
                    color: #e2e8f0;
                    padding: 6px;
                    font-size: 13px;
                }
                QListWidget::item {
                    padding: 6px;
                    border-bottom: 1px solid #1e293b;
                    border-radius: 4px;
                }
                QListWidget::item:selected {
                    background-color: #1e3a8a;
                    color: #ffffff;
                }
            """)
            files_layout.addWidget(self.file_list)

            # File action buttons
            file_btn_layout = QHBoxLayout()
            self.add_btn = QPushButton("➕ Add .deb Files...")
            self.add_btn.clicked.connect(self.choose_files)
            self.remove_btn = QPushButton("➖ Remove Selected")
            self.remove_btn.clicked.connect(self.remove_selected)
            self.clear_btn = QPushButton("🗑 Clear All")
            self.clear_btn.clicked.connect(self.clear_files)

            file_btn_layout.addWidget(self.add_btn)
            file_btn_layout.addWidget(self.remove_btn)
            file_btn_layout.addWidget(self.clear_btn)
            file_btn_layout.addStretch()
            self.file_count_label = QLabel("0 packages queued (Drag & drop files above)")
            self.file_count_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
            file_btn_layout.addWidget(self.file_count_label)
            files_layout.addLayout(file_btn_layout)

            main_layout.addWidget(files_group)

            # Output & Settings Section
            settings_group = QGroupBox("Destination & Build Options")
            settings_layout = QVBoxLayout(settings_group)

            # Output folder radios
            out_row = QHBoxLayout()
            self.out_same_dir = QRadioButton("Save in same directory as source .deb package")
            self.out_custom_dir = QRadioButton("Save in custom destination directory:")
            self.out_same_dir.setChecked(True)

            self.out_button_group = QButtonGroup(self)
            self.out_button_group.addButton(self.out_same_dir)
            self.out_button_group.addButton(self.out_custom_dir)
            self.out_button_group.buttonToggled.connect(self.toggle_output_mode)

            out_row.addWidget(self.out_same_dir)
            out_row.addWidget(self.out_custom_dir)
            out_row.addStretch()
            settings_layout.addLayout(out_row)

            # Custom folder picker
            custom_path_row = QHBoxLayout()
            self.custom_path_edit = QLineEdit()
            self.custom_path_edit.setPlaceholderText("Select destination directory...")
            self.custom_path_edit.setEnabled(False)
            default_dir = initial_output if initial_output else str(Path.home() / "Downloads")
            self.custom_path_edit.setText(default_dir)

            self.browse_dir_btn = QPushButton("Browse...")
            self.browse_dir_btn.setEnabled(False)
            self.browse_dir_btn.clicked.connect(self.choose_output_dir)

            custom_path_row.addWidget(self.custom_path_edit)
            custom_path_row.addWidget(self.browse_dir_btn)
            settings_layout.addLayout(custom_path_row)

            # Checkbox Options
            options_grid = QHBoxLayout()
            self.cb_keep_version = QCheckBox("Keep package version (-k)")
            self.cb_keep_version.setToolTip("Preserve exact upstream release version without alien bumping it")
            self.cb_keep_version.setChecked(True)

            self.cb_scripts = QCheckBox("Include maintainer scripts (-c)")
            self.cb_scripts.setToolTip("Include pre/post installation scripts in the generated RPM")
            self.cb_scripts.setChecked(True)

            self.cb_fixperms = QCheckBox("Fix permissions (--fixperms)")
            self.cb_fixperms.setToolTip("Munge and fix file permissions and owners")
            self.cb_fixperms.setChecked(False)

            self.cb_fakeroot = QCheckBox("Use fakeroot")
            self.cb_fakeroot.setToolTip("Run alien within fakeroot to emulate root file ownership")
            self.cb_fakeroot.setChecked(True)

            options_grid.addWidget(self.cb_keep_version)
            options_grid.addWidget(self.cb_scripts)
            options_grid.addWidget(self.cb_fixperms)
            options_grid.addWidget(self.cb_fakeroot)
            options_grid.addStretch()
            settings_layout.addLayout(options_grid)

            post_opts = QHBoxLayout()
            self.cb_open_folder = QCheckBox("Open destination folder when finished")
            self.cb_open_folder.setChecked(True)

            self.cb_auto_install = QCheckBox("Install RPM with DNF after conversion")
            self.cb_auto_install.setChecked(False)

            post_opts.addWidget(self.cb_open_folder)
            post_opts.addWidget(self.cb_auto_install)
            post_opts.addStretch()
            settings_layout.addLayout(post_opts)

            main_layout.addWidget(settings_group)

            # Progress & Control Bar
            progress_layout = QVBoxLayout()
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setTextVisible(True)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #334155;
                    border-radius: 4px;
                    text-align: center;
                    background: #0f172a;
                    color: #ffffff;
                    height: 22px;
                    font-weight: 500;
                }
                QProgressBar::chunk {
                    background-color: #3b82f6;
                    border-radius: 3px;
                }
            """)
            progress_layout.addWidget(self.progress_bar)

            btn_row = QHBoxLayout()
            self.convert_btn = QPushButton("🚀 Convert to RPM")
            self.convert_btn.setEnabled(False)
            self.convert_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 8px 24px;
                    border: none;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
                QPushButton:disabled {
                    background-color: #334155;
                    color: #64748b;
                }
            """)
            self.convert_btn.clicked.connect(self.start_conversion)

            self.cancel_btn = QPushButton("⏹ Cancel")
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.clicked.connect(self.cancel_conversion)

            self.open_output_btn = QPushButton("📂 Open Destination")
            self.open_output_btn.setEnabled(False)
            self.open_output_btn.clicked.connect(self.open_current_output)

            self.install_rpm_btn = QPushButton("📥 Install RPM")
            self.install_rpm_btn.setEnabled(False)
            self.install_rpm_btn.clicked.connect(self.install_generated_rpm)

            btn_row.addWidget(self.convert_btn)
            btn_row.addWidget(self.cancel_btn)
            btn_row.addStretch()
            btn_row.addWidget(self.open_output_btn)
            btn_row.addWidget(self.install_rpm_btn)
            progress_layout.addLayout(btn_row)

            main_layout.addLayout(progress_layout)

            # Real-time Console Log
            log_group = QGroupBox("Build Log Output")
            log_layout = QVBoxLayout(log_group)

            self.log_view = QTextEdit()
            self.log_view.setReadOnly(True)
            self.log_view.setStyleSheet("""
                QTextEdit {
                    background-color: #0b0f19;
                    color: #cbd5e1;
                    font-family: monospace;
                    font-size: 12px;
                    border: 1px solid #1e293b;
                    border-radius: 4px;
                }
            """)
            log_layout.addWidget(self.log_view)

            log_bar = QHBoxLayout()
            clear_log_btn = QPushButton("Clear Log")
            clear_log_btn.clicked.connect(self.log_view.clear)
            copy_log_btn = QPushButton("Copy Log")
            copy_log_btn.clicked.connect(self.copy_log)
            log_bar.addWidget(clear_log_btn)
            log_bar.addWidget(copy_log_btn)
            log_bar.addStretch()
            log_layout.addLayout(log_bar)

            main_layout.addWidget(log_group)

        def check_dependencies_banner(self):
            missing = check_missing_tools()
            if missing:
                missing_str = ", ".join(t for t, _ in missing)
                pkg_str = " ".join(p for _, p in missing)
                self.dep_label.setText(f"⚠️ Missing required packaging tools: {missing_str} (Package: {pkg_str})")
                self.dep_banner.setVisible(True)
                self.status_badge.setText("Missing Tools")
                self.status_badge.setStyleSheet("""
                    background-color: #78350f;
                    color: #fbbf24;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 4px 10px;
                    border-radius: 12px;
                    border: 1px solid #d97706;
                """)
            else:
                self.dep_banner.setVisible(False)
                self.status_badge.setText("Ready")
                self.status_badge.setStyleSheet("""
                    background-color: #065f46;
                    color: #34d399;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 4px 10px;
                    border-radius: 12px;
                    border: 1px solid #059669;
                """)

        def install_dependencies(self):
            missing = check_missing_tools()
            if not missing:
                return
            pkgs = [pkg for _, pkg in missing]
            cmd = ["pkexec", "dnf", "install", "-y"] + pkgs
            self.log_message(f"Installing missing packages: {' '.join(pkgs)}...", "cmd")
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.stdout:
                    self.log_message(proc.stdout, "info")
                if proc.returncode == 0:
                    QMessageBox.information(self, "Success", "Dependencies installed successfully!")
                    self.check_dependencies_banner()
                else:
                    QMessageBox.warning(self, "Installation Failed", f"Could not install packages:\n{proc.stderr}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to execute pkexec: {e}")

        def toggle_output_mode(self):
            is_custom = self.out_custom_dir.isChecked()
            self.custom_path_edit.setEnabled(is_custom)
            self.browse_dir_btn.setEnabled(is_custom)

        def choose_output_dir(self):
            dir_name = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.custom_path_edit.text())
            if dir_name:
                self.custom_path_edit.setText(dir_name)

        def choose_files(self):
            files, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Debian Packages",
                str(Path.home() / "Downloads"),
                "Debian Packages (*.deb);;All Files (*)"
            )
            if files:
                self.add_files(files)

        def add_files(self, file_paths):
            added_any = False
            for f in file_paths:
                p = Path(f).resolve()
                if p.is_file() and p.name.endswith(".deb") and str(p) not in self.queued_files:
                    self.queued_files.append(str(p))
                    size_str = format_size(p.stat().st_size)
                    item = QListWidgetItem(f"📦 {p.name}  ({size_str}) — {p.parent}")
                    item.setData(Qt.ItemDataRole.UserRole, str(p))
                    self.file_list.addItem(item)
                    added_any = True
            if added_any:
                self.update_file_count()

        def remove_selected(self):
            for item in self.file_list.selectedItems():
                path = item.data(Qt.ItemDataRole.UserRole)
                if path in self.queued_files:
                    self.queued_files.remove(path)
                self.file_list.takeItem(self.file_list.row(item))
            self.update_file_count()

        def clear_files(self):
            self.queued_files.clear()
            self.file_list.clear()
            self.update_file_count()

        def update_file_count(self):
            count = len(self.queued_files)
            msg = f"{count} package{'s' if count != 1 else ''} queued"
            if count == 0:
                msg += " (Drag & drop files above)"
            self.file_count_label.setText(msg)
            self.convert_btn.setEnabled(count > 0)

        def log_message(self, text, tag="info"):
            color_map = {
                "info": "#94a3b8",
                "cmd": "#38bdf8",
                "success": "#4ade80",
                "error": "#f87171"
            }
            color = color_map.get(tag, "#cbd5e1")
            escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            self.log_view.append(f"<span style='color: {color};'>{escaped}</span>")
            self.log_view.moveCursor(QTextCursor.MoveOperation.End)

        def copy_log(self):
            clipboard = QApplication.clipboard()
            clipboard.setText(self.log_view.toPlainText())
            QMessageBox.information(self, "Copied", "Log output copied to clipboard.")

        def start_conversion(self):
            if not self.queued_files:
                return

            missing = check_missing_tools()
            if missing:
                missing_str = ", ".join(t for t, _ in missing)
                QMessageBox.critical(self, "Missing Tools", f"Please install {missing_str} before converting.")
                return

            options = {
                "output_dir": self.custom_path_edit.text().strip() if self.out_custom_dir.isChecked() else None,
                "keep_version": self.cb_keep_version.isChecked(),
                "scripts": self.cb_scripts.isChecked(),
                "fixperms": self.cb_fixperms.isChecked(),
                "use_fakeroot": self.cb_fakeroot.isChecked(),
            }

            self.convert_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            self.open_output_btn.setEnabled(False)
            self.install_rpm_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            self.status_badge.setText("Converting...")
            self.status_badge.setStyleSheet("""
                background-color: #1e3a8a;
                color: #60a5fa;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 12px;
                border: 1px solid #2563eb;
            """)

            self.worker = ConversionWorker(list(self.queued_files), options)
            self.worker.log_signal.connect(self.log_message)
            self.worker.progress_signal.connect(self.on_worker_progress)
            self.worker.finished_signal.connect(self.on_worker_finished)
            self.worker.start()

        def cancel_conversion(self):
            if self.worker and self.worker.isRunning():
                self.worker.cancel()
                self.cancel_btn.setEnabled(False)
                self.log_message("Abort requested by user.", "error")

        def on_worker_progress(self, current, total, name):
            if total > 0:
                pct = int((current / total) * 100)
                self.progress_bar.setValue(pct)
                self.progress_bar.setFormat(f"{pct}% ({current}/{total}) - {name}")

        def on_worker_finished(self, success, rpms, error_msg):
            self.convert_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.last_rpms = rpms

            if success and rpms:
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("Completed Successfully! (100%)")
                self.status_badge.setText("Success")
                self.status_badge.setStyleSheet("""
                    background-color: #065f46;
                    color: #34d399;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 4px 10px;
                    border-radius: 12px;
                    border: 1px solid #059669;
                """)
                self.open_output_btn.setEnabled(True)
                self.install_rpm_btn.setEnabled(True)

                if self.cb_open_folder.isChecked():
                    self.open_current_output()

                if self.cb_auto_install.isChecked():
                    self.install_generated_rpm()
            else:
                self.status_badge.setText("Failed")
                self.status_badge.setStyleSheet("""
                    background-color: #7f1d1d;
                    color: #f87171;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 4px 10px;
                    border-radius: 12px;
                    border: 1px solid #dc2626;
                """)
                if error_msg != "Cancelled":
                    QMessageBox.warning(self, "Conversion Notice", f"One or more conversions had issues:\n{error_msg}")

        def open_current_output(self):
            if self.out_custom_dir.isChecked():
                target = Path(self.custom_path_edit.text()).resolve()
            elif self.last_rpms:
                target = self.last_rpms[0].parent
            elif self.queued_files:
                target = Path(self.queued_files[0]).parent
            else:
                target = Path.home()

            if target.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

        def install_generated_rpm(self):
            if not self.last_rpms:
                QMessageBox.information(self, "No RPMs", "No generated RPM packages available to install.")
                return

            rpm_paths = [str(r) for r in self.last_rpms if r.exists()]
            if not rpm_paths:
                QMessageBox.warning(self, "Error", "Generated RPM files were not found on disk.")
                return

            reply = QMessageBox.question(
                self,
                "Install Packages",
                f"Install {len(rpm_paths)} package(s) using DNF?\n\n" + "\n".join(Path(r).name for r in rpm_paths),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                cmd = ["pkexec", "dnf", "install", "-y"] + rpm_paths
                self.log_message(f"Installing packages: {' '.join(cmd)}", "cmd")
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.stdout:
                    self.log_message(proc.stdout, "info")
                if proc.returncode == 0:
                    QMessageBox.information(self, "Success", "Packages installed successfully!")
                else:
                    QMessageBox.warning(self, "Installation Failed", f"DNF failed with error:\n{proc.stderr}")


def launch_gui(initial_files=None, initial_output=None):
    if not QT_AVAILABLE:
        print("[ERROR] Neither PyQt6 nor PySide6 is installed.")
        print("Please install PyQt6 with: sudo dnf install python3-pyqt6")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("deb2rpm")
    app.setDesktopFileName("deb2rpm.desktop")

    window = Deb2RpmWindow(initial_files, initial_output)
    window.show()
    sys.exit(app.exec())

def main():
    parser = argparse.ArgumentParser(
        description="Convert Debian packages (.deb) to RPM (.rpm) packages for Fedora Linux"
    )
    parser.add_argument("files", nargs="*", help="Debian package (.deb) file(s) to convert")
    parser.add_argument("-o", "--output", help="Output directory for generated RPM package(s)")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode without GUI")
    parser.add_argument("-k", "--keep-version", action="store_true", default=True, help="Preserve upstream version (alien -k)")
    parser.add_argument("-c", "--scripts", action="store_true", default=True, help="Include maintainer scripts (alien -c)")
    parser.add_argument("--fixperms", action="store_true", help="Sanitize permissions (alien --fixperms)")
    parser.add_argument("-i", "--install", action="store_true", help="Install RPM package after conversion (CLI only)")

    # If running with --cli or without graphical display, run CLI
    if "--cli" in sys.argv or not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        args = parser.parse_args()
        if not args.files:
            parser.print_help()
            sys.exit(1)
        run_cli(args)
        return

    parsed, _ = parser.parse_known_args()
    launch_gui(parsed.files, parsed.output)

if __name__ == "__main__":
    main()
