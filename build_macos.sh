#!/bin/bash
# ============================================================
#  MakerStl — macOS build script
#  Run from repo root after installing all deps:
#    pip3 install -r requirements.txt pyinstaller
# ============================================================

set -e

PYTHON=${PYTHON:-/Library/Frameworks/Python.framework/Versions/3.13/bin/python3}

echo "[1/3] Building .app with PyInstaller ..."
$PYTHON -m PyInstaller MakerStl.spec --noconfirm

echo "[2/3] Creating DMG ..."
mkdir -p builds
rm -rf /tmp/MakerStl-dmg
mkdir -p /tmp/MakerStl-dmg
cp -R dist/MakerStl.app /tmp/MakerStl-dmg/
ln -s /Applications /tmp/MakerStl-dmg/Applications
hdiutil create -volname "MakerStl" -srcfolder /tmp/MakerStl-dmg -ov -format UDZO builds/MakerStl.dmg
rm -rf /tmp/MakerStl-dmg

echo "[3/3] Done!"
echo ""
echo "  Output: builds/MakerStl.dmg"
echo ""
