#!/usr/bin/env bash
# Installs a desktop launcher for the built VidKonverter binary so it can
# be started from the application menu/taskbar instead of double-clicking
# the raw executable in a file manager (which GNOME Files et al. will
# challenge with an "untrusted executable" prompt every single time).
#
# Usage:
#   packaging/install_linux.sh [path/to/VidKonverter]
#
# Defaults to dist/VidKonverter relative to the repo root if no path is
# given.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_PATH="${1:-$SCRIPT_DIR/../dist/VidKonverter}"
BIN_PATH="$(cd "$(dirname "$BIN_PATH")" && pwd)/$(basename "$BIN_PATH")"

if [ ! -f "$BIN_PATH" ]; then
    echo "error: executable not found at $BIN_PATH" >&2
    exit 1
fi

chmod +x "$BIN_PATH"

APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
DESKTOP_FILE="$APPS_DIR/vidkonverter.desktop"

sed "s|__EXEC_PATH__|$BIN_PATH|" "$SCRIPT_DIR/videoconverter.desktop.in" > "$DESKTOP_FILE"
chmod +x "$DESKTOP_FILE"

# Install the app icon into the user's icon theme so the Icon=vidkonverter
# line in the desktop entry (above) actually resolves to something.
ICON_SRC="$SCRIPT_DIR/../videoconverter/icons/vidkonverter-app-icon.png"
if [ -f "$ICON_SRC" ]; then
    ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
    mkdir -p "$ICON_DIR"
    cp "$ICON_SRC" "$ICON_DIR/vidkonverter.png"
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    fi
fi

# Mark the launcher as trusted so file managers that store this per-file
# (GNOME Files/Nautilus) don't prompt "Allow Launching?" on first use.
if command -v gio >/dev/null 2>&1; then
    gio set "$DESKTOP_FILE" metadata::trusted true 2>/dev/null || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

echo "Installed launcher: $DESKTOP_FILE"
echo "VidKonverter should now appear in your application menu."
