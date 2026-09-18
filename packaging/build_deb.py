#!/usr/bin/env python3
"""Build a .deb from the PyInstaller binary in dist/ (run packaging/build.py
first - this doesn't build it for you).

Usage:
    python3 packaging/build_deb.py

Output: dist/vidkonverter_<version>_amd64.deb
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from videoconverter._version import __version__  # noqa: E402

BINARY = ROOT / "dist" / "VidKonverter"
ARCH = "amd64"
MAINTAINER = "James <james@farfromsquare.io>"


def main():
    if not BINARY.is_file():
        sys.exit(f"error: {BINARY} not found - run packaging/build.py first")
    if shutil.which("dpkg-deb") is None:
        sys.exit("error: dpkg-deb not found (install the 'dpkg' package)")

    staging = ROOT / "build" / "deb-staging"
    if staging.exists():
        shutil.rmtree(staging)

    bin_dir = staging / "usr" / "bin"
    apps_dir = staging / "usr" / "share" / "applications"
    icon_dir = staging / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps"
    doc_dir = staging / "usr" / "share" / "doc" / "vidkonverter"
    debian_dir = staging / "DEBIAN"
    for d in (bin_dir, apps_dir, icon_dir, doc_dir, debian_dir):
        d.mkdir(parents=True, exist_ok=True)

    shutil.copy2(BINARY, bin_dir / "vidkonverter")
    (bin_dir / "vidkonverter").chmod(0o755)
    shutil.copy2(PACKAGING / "vidkonverter.desktop", apps_dir / "vidkonverter.desktop")
    shutil.copy2(
        ROOT / "videoconverter" / "icons" / "vidkonverter-app-icon.png",
        icon_dir / "vidkonverter.png",
    )

    # Debian's machine-readable copyright format (DEP-5) - a short
    # declaration, not the full license text (which is what LICENSE, at
    # the project root, is for; the About dialog's "View License" button
    # opens that copy directly rather than this one).
    copyright_text = """Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: vidkonverter
Source: https://github.com/cooleryoungerbrother/vidkonverter

Files: *
Copyright: 2026 James Burrows
License: GPL-3.0-only

License: GPL-3.0-only
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License, version 3, as
 published by the Free Software Foundation.
 .
 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 GNU General Public License for more details.
 .
 You should have received a copy of the GNU General Public License
 along with this program. If not, see <https://www.gnu.org/licenses/>.
"""
    (doc_dir / "copyright").write_text(copyright_text)

    installed_size_kb = sum(
        f.stat().st_size for f in staging.rglob("*") if f.is_file()
    ) // 1024

    control = f"""Package: vidkonverter
Version: {__version__}
Section: video
Priority: optional
Architecture: {ARCH}
Installed-Size: {installed_size_kb}
Maintainer: {MAINTAINER}
Recommends: ffmpeg
Description: Convert video files with ffmpeg
 VidKonverter is a desktop GUI for converting and batch-converting video
 files with ffmpeg - container/codec selection, crop, trim, and alpha
 channel handling.
"""
    (debian_dir / "control").write_text(control)

    dist_dir = ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)
    out_path = dist_dir / f"vidkonverter_{__version__}_{ARCH}.deb"

    subprocess.check_call(
        ["dpkg-deb", "--root-owner-group", "--build", str(staging), str(out_path)]
    )
    print(f"\nBuilt {out_path}")


if __name__ == "__main__":
    main()
