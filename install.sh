#!/bin/bash
set -euo pipefail

# deb2rpm-gui installer script for Fedora Linux

PREFIX="${HOME}/.local"
SYSTEM_INSTALL=false

for arg in "$@"; do
    case "$arg" in
        --system)
            SYSTEM_INSTALL=true
            PREFIX="/usr/local"
            ;;
        --help|-h)
            echo "Usage: $0 [--system]"
            echo "  --system    Install system-wide to /usr/local (requires root)"
            echo "  (default)   Install for current user to ~/.local"
            exit 0
            ;;
    esac
done

if [ "$SYSTEM_INSTALL" = true ] && [ "$EUID" -ne 0 ]; then
    echo "Error: --system install requires root privileges. Please run with sudo." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installing DEB to RPM Converter (deb2rpm) ==="
echo "Destination prefix: $PREFIX"

# Check dependencies
MISSING_PKGS=()
if ! command -v alien &>/dev/null; then
    MISSING_PKGS+=("alien")
fi
if ! command -v fakeroot &>/dev/null; then
    MISSING_PKGS+=("fakeroot")
fi
if ! command -v rpmbuild &>/dev/null; then
    MISSING_PKGS+=("rpm-build")
fi
if ! python3 -c "import PyQt6" &>/dev/null && ! python3 -c "import PySide6" &>/dev/null; then
    MISSING_PKGS+=("python3-pyqt6")
fi

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo ""
    echo "[!] Notice: Some optional or required dependencies are missing: ${MISSING_PKGS[*]}"
    echo "    You can install them on Fedora with:"
    echo "    sudo dnf install -y ${MISSING_PKGS[*]}"
    echo ""
fi

# Target directories
BIN_DIR="${PREFIX}/bin"
APP_DIR="${PREFIX}/share/applications"
ICON_DIR="${PREFIX}/share/icons/hicolor/scalable/apps"

mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

# Install executable
echo "[*] Installing binary to ${BIN_DIR}/deb2rpm-gui..."
install -m 755 "${SCRIPT_DIR}/deb2rpm-gui.py" "${BIN_DIR}/deb2rpm-gui"
ln -sf "deb2rpm-gui" "${BIN_DIR}/deb2rpm"

# Install icon
echo "[*] Installing icon to ${ICON_DIR}/deb2rpm.svg..."
install -m 644 "${SCRIPT_DIR}/deb2rpm.svg" "${ICON_DIR}/deb2rpm.svg"

# Install desktop entry
echo "[*] Installing desktop entry to ${APP_DIR}/deb2rpm.desktop..."
install -m 644 "${SCRIPT_DIR}/deb2rpm.desktop" "${APP_DIR}/deb2rpm.desktop"

# Refresh desktop database & icon cache
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "${PREFIX}/share/icons/hicolor" 2>/dev/null || true
fi

echo ""
echo "============================================================"
echo " [SUCCESS] deb2rpm has been installed successfully!"
echo "============================================================"
echo ""
echo " You can now:"
echo "   1. Launch 'DEB to RPM Converter' from your Application Menu"
echo "   2. Right-click any .deb file in your file manager and open with deb2rpm"
echo "   3. Run 'deb2rpm' or 'deb2rpm-gui' in the terminal"
echo "   4. Convert from CLI: deb2rpm --cli package.deb"
echo ""
