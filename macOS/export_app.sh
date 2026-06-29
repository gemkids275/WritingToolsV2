#!/bin/bash
set -e

# --- Configuration ---
# This script prepares a macOS .app for distribution by:
# 1. Clearing quarantine attributes
# 2. Re-signing the app with an ad-hoc signature (crucial for M1/M2/M3 chips)
# 3. Packaging it into a DMG with an /Applications shortcut

APP_PATH="$1"
STAGING_DIR="dmg_staging"

# --- Validation ---
if [ -z "$APP_PATH" ]; then
    echo "Usage: ./export_app.sh /path/to/AI_Shortcuts.app"
    exit 1
fi

if [ ! -d "$APP_PATH" ]; then
    echo "Error: '$APP_PATH' not found."
    exit 1
fi

APP_NAME=$(basename "$APP_PATH" .app)
OUTPUT_DIR=$(dirname "$APP_PATH")
DMG_PATH="$OUTPUT_DIR/$APP_NAME.dmg"

echo "🚀 Preparing distribution for: $APP_NAME"
echo "--------------------------------------------------------"

# 1. Clear quarantine and extended attributes
echo "→ Clearing quarantine attributes..."
xattr -cr "$APP_PATH"

# 2. Ad-hoc Signing (Fixes 'Can't be opened' errors on Apple Silicon)
# We use the commands from your feedback
echo "→ Signing application with ad-hoc signature..."
codesign --deep --force --sign - "$APP_PATH"

# 3. Create DMG structure with shortcut
echo "→ Creating DMG staging area..."
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -R "$APP_PATH" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

# 4. Create DMG Package
# Using UDZO format for compression
echo "→ Building DMG package..."
hdiutil create -volname "$APP_NAME" \
    -srcfolder "$STAGING_DIR" \
    -ov -format UDZO \
    "$DMG_PATH"

# 5. Cleanup staging
rm -rf "$STAGING_DIR"

echo ""
echo "✅ Script complete!"
echo "📍 DMG created at: $DMG_PATH"
echo "--------------------------------------------------------"
echo "NOTE: If someone still gets a 'Damaged' error after installing,"
echo "have them run this command in their Terminal:"
echo "xattr -cr /Applications/\"$APP_NAME.app\""
echo "--------------------------------------------------------"
