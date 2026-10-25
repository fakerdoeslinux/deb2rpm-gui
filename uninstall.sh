#!/bin/bash
set -euo pipefail

# deb2rpm-gui uninstaller script for Fedora Linux

PREFIX="${HOME}/.local"
SYSTEM_UNINSTALL=false

for arg in "$@"; do
    case "$arg" in
        --system)
            SYSTEM_UNINSTALL=true
            PREFIX="/usr/local"
            ;;
        --help|-h)
            echo "Usage: $0 [--system]"
            echo "  --system    Uninstall system-wide installation (/usr/local)"
            echo "  (default)   Uninstall current user installation (~/.local)"
            exit 0
            ;;
    esac
done

if [ "$SYSTEM_UNINSTALL" = true ] && [ "$EUID" -ne 0 ]; then
    echo "Error: --system uninstall requires root privileges. Please run with sudo." >&2
    exit 1
fi

echo "=== Uninstalling DEB to RPM Converter (deb2rpm) ==="
echo "Target prefix: $PREFIX"

rm -f "${PREFIX}/bin/deb2rpm-gui"
rm -f "${PREFIX}/bin/deb2rpm"
rm -f "${PREFIX}/share/applications/deb2rpm.desktop"
rm -f "${PREFIX}/share/icons/hicolor/scalable/apps/deb2rpm.svg"

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "${PREFIX}/share/applications" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "${PREFIX}/share/icons/hicolor" 2>/dev/null || true
fi

echo "[SUCCESS] deb2rpm uninstalled successfully."
