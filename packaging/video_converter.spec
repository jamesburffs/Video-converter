# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for VidKonverter.

Build on each target OS separately (PyInstaller does not cross-compile):
    python packaging/build.py

Output lands in dist/ - a single VidKonverter(.exe) file on Linux/Windows,
or VidKonverter.app on macOS.
"""
import os
import sys

main_script = os.path.join(SPECPATH, "..", "main.py")
icons_dir = os.path.join(SPECPATH, "..", "videoconverter", "icons")
# The About dialog's "View License" button looks for this next to itself
# (os.path.dirname(__file__)) at runtime - same relative location as source,
# so it resolves correctly whether running from a checkout or this build.
license_file = os.path.join(SPECPATH, "..", "videoconverter", "LICENSE")

a = Analysis(
    [main_script],
    pathex=[],
    binaries=[],
    datas=[
        (icons_dir, os.path.join("videoconverter", "icons")),
        (license_file, "videoconverter"),
    ],
    hiddenimports=["PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="VidKonverter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="VidKonverter.app",
        # PyInstaller needs a .icns for macOS (the source PNG in
        # videoconverter/icons/ isn't directly usable here) - generate one
        # with iconutil/sips and point this at it when building on macOS.
        icon=None,
        bundle_identifier="com.cooleryoungerbrother.vidkonverter",
        info_plist={"NSHighResolutionCapable": True},
    )
