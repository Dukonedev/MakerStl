# -*- mode: python ; coding: utf-8 -*-
# Cross-platform PyInstaller spec — works on macOS and Windows.

import sys
import os

block_cipher = None
is_macos = sys.platform == "darwin"
is_win = sys.platform == "win32"

# --- icon ---
if is_macos:
    icon_path = 'resources/app-icon.icns'
elif is_win:
    icon_path = 'resources/app-icon.ico'
else:
    icon_path = None

# --- data files ---
datas = [
    ('Banner.jpeg', '.'),
    ('splash_screen.jpeg', '.'),
]
if is_macos:
    datas.append(('resources/app-icon.icns', 'resources'))
elif is_win:
    # bundle .ico if it exists
    if os.path.exists('resources/app-icon.ico'):
        datas.append(('resources/app-icon.ico', 'resources'))

a = Analysis(
    ['run.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'shapely',
        'shapely.ops',
        'shapely.geometry',
        'scipy',
        'scipy.ndimage',
        'numpy',
        'fontTools',
        'fontTools.ttLib',
        'fontTools.pens.recordingPen',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'lxml',
        'lxml.etree',
        'mapbox_earcut',
        'pyclipper',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MakerStl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None if not is_macos else None,
    entitlements_file=None,
    icon=icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MakerStl',
)

# macOS only: create .app bundle
if is_macos:
    app = BUNDLE(
        coll,
        name='MakerStl.app',
        icon='resources/app-icon.icns',
        bundle_identifier='com.makerstl.app',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',
        },
    )
