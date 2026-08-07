#!/bin/bash
# Installs the PostRipM4B application icon (Linux .desktop integration)
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICON_PNG="$REPO_DIR/assets/icon.png"
ICON_SVG="$REPO_DIR/assets/icon.svg"
DESKTOP="postrip-m4b.desktop"

HICOLOR_DIR="$HOME/.local/share/icons/hicolor"

echo "Installing PostRipM4B launcher icon for the current user..."

# Icon (standard hicolor icon theme).
# Install a scalable SVG (best for KDE/GTK scaling) plus size-specific PNGs.
if [ -f "$ICON_SVG" ]; then
    mkdir -p "$HICOLOR_DIR/scalable/apps"
    cp "$ICON_SVG" "$HICOLOR_DIR/scalable/apps/postrip-m4b.svg"
    echo "  Icon -> $HICOLOR_DIR/scalable/apps/postrip-m4b.svg"
fi
if [ -f "$ICON_PNG" ]; then
    for SIZE in 48 128 256 512; do
        ICON_DIR="$HICOLOR_DIR/${SIZE}x${SIZE}/apps"
        mkdir -p "$ICON_DIR"
        cp "$ICON_PNG" "$ICON_DIR/postrip-m4b.png"
        echo "  Icon -> $ICON_DIR/postrip-m4b.png"
    done
fi

# Ensure the icon theme has an index.theme, otherwise icon lookup/cache ignores it
INDEX_THEME="$HICOLOR_DIR/index.theme"
if [ ! -f "$INDEX_THEME" ]; then
cat > "$INDEX_THEME" <<EOF
[Icon Theme]
Name=Hicolor
Comment=Fallback icon theme
Inherits=hicolor
Directories=$(for SIZE in 16 22 24 32 36 48 64 72 96 128 192 256 512; do printf "%sx%s/apps," "$SIZE" "$SIZE"; done)scalable/apps
Hidden=false

[48x48/apps]
Size=48
Context=Applications
Type=Threshold

[128x128/apps]
Size=128
Context=Applications
Type=Threshold

[256x256/apps]
MinSize=64
Size=256
MaxSize=256
Context=Applications
Type=Scalable

[512x512/apps]
MinSize=64
Size=512
MaxSize=512
Context=Applications
Type=Scalable

[scalable/apps]
MinSize=16
Size=512
MaxSize=512
Context=Applications
Type=Scalable
EOF
echo "  Icon theme index -> $INDEX_THEME"
fi

# Desktop entry
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/$DESKTOP" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=PostRipM4B Audiobook Converter
GenericName=Audiobook Converter
Comment=Convert MP3 audiobooks to M4B
Exec=$REPO_DIR/PostRipM4B.sh --gui
Icon=postrip-m4b
Terminal=false
Categories=AudioVideo;Audio;Multimedia;
StartupNotify=true
StartupWMClass=postrip-m4b
EOF
chmod +x "$APPS_DIR/$DESKTOP"
echo "  Desktop entry -> $APPS_DIR/$DESKTOP"

# Refresh desktop database so menus pick it up (ignore if not present)
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1 && [ -d "$HOME/.local/share/icons/hicolor" ]; then
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

# Refresh the KDE menu/service database so search and launchers pick up the entry
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null 2>&1 || true
fi

echo "Done. You can now find \"PostRipM4B Audiobook Converter\" in your app menu."
echo "Tip: If your launcher still shows the generic icon, log out and back in."
