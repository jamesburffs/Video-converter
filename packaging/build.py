#!/usr/bin/env python3
"""Build a single-file VidKonverter executable for the CURRENT platform.

PyInstaller does not cross-compile, so this must be run separately on each
target OS:
    Linux:   python3 packaging/build.py
    macOS:   python3 packaging/build.py
    Windows: python packaging\\build.py

ffmpeg/ffprobe are NOT bundled - the app detects and can help install them
at runtime (see videoconverter/ffmpeg_installer.py). This keeps the build
small and avoids shipping stale/oversized codec binaries.

Output is written to dist/ - VidKonverter (Linux), VidKonverter.exe
(Windows), or VidKonverter.app (macOS).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = Path(__file__).resolve().parent / "video_converter.spec"


def main():
    subprocess.check_call(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC)],
        cwd=ROOT,
    )
    print("\nBuild complete. See the dist/ folder.")


if __name__ == "__main__":
    main()
