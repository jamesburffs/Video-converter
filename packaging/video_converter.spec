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
    # Windows only (ignored elsewhere): the .exe's own icon in Explorer,
    # the taskbar and shortcuts. PyInstaller converts the PNG to .ico
    # itself when Pillow is installed (see requirements-build.txt).
    icon=(
        os.path.join(icons_dir, "vidkonverter-app-icon.png")
        if sys.platform == "win32" else None
    ),
)

if sys.platform == "darwin":
    import subprocess
    import tempfile

    # The Dock icon is set at runtime by app.setWindowIcon() (see
    # __main__.py) and needs nothing here - but the Finder/Launchpad icon
    # for the .app bundle itself is a static resource baked in at build
    # time (Info.plist's CFBundleIconFile, generated below), which is why
    # it showed PyInstaller's own generic icon before this existed. macOS
    # needs a .icns specifically - the source PNG isn't directly usable -
    # built here via sips/iconutil (both part of the base OS, no extra
    # install needed) rather than checked in, so it always matches
    # whatever's currently in videoconverter/icons/.
    icns_file = os.path.join(SPECPATH, "..", "build", "vidkonverter.icns")
    if not os.path.isfile(icns_file):
        source_png = os.path.join(icons_dir, "vidkonverter-app-icon.png")
        with tempfile.TemporaryDirectory() as tmp:
            iconset = os.path.join(tmp, "vidkonverter.iconset")
            os.makedirs(iconset)
            # Each @2x entry is the same nominal point size at double the
            # pixel dimensions, for Retina displays - the full set
            # iconutil expects in a .iconset directory.
            sizes = [
                (16, "icon_16x16.png"), (32, "icon_16x16@2x.png"),
                (32, "icon_32x32.png"), (64, "icon_32x32@2x.png"),
                (128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
                (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
                (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png"),
            ]
            for size, filename in sizes:
                subprocess.run(
                    [
                        "sips", "-z", str(size), str(size), source_png,
                        "--out", os.path.join(iconset, filename),
                    ],
                    check=True, capture_output=True,
                )
            os.makedirs(os.path.dirname(icns_file), exist_ok=True)
            subprocess.run(
                ["iconutil", "-c", "icns", iconset, "-o", icns_file],
                check=True, capture_output=True,
            )

    app = BUNDLE(
        exe,
        name="VidKonverter.app",
        icon=icns_file,
        bundle_identifier="com.cooleryoungerbrother.vidkonverter",
        info_plist={"NSHighResolutionCapable": True},
    )
