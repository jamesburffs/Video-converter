#!/usr/bin/env python3
"""Build an .rpm from the PyInstaller binary in dist/ (run packaging/build.py
first - this doesn't build it for you).

Usage:
    python3 packaging/build_rpm.py

Output: dist/vidkonverter-<version>-1.<dist>.x86_64.rpm
"""
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from videoconverter._version import __version__  # noqa: E402

BINARY = ROOT / "dist" / "VidKonverter"
SPEC = PACKAGING / "rpm" / "vidkonverter.spec"


def main():
    if not BINARY.is_file():
        sys.exit(f"error: {BINARY} not found - run packaging/build.py first")
    if shutil.which("rpmbuild") is None:
        sys.exit("error: rpmbuild not found (install the 'rpm-build' package)")

    topdir = ROOT / "build" / "rpmbuild"
    for sub in ("BUILD", "RPMS", "SOURCES", "SPECS", "SRPMS"):
        (topdir / sub).mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["VK_PROJECT_ROOT"] = str(ROOT)
    env["VK_VERSION"] = __version__

    subprocess.check_call(
        ["rpmbuild", "--define", f"_topdir {topdir}", "-bb", str(SPEC)],
        env=env,
    )

    built = glob.glob(str(topdir / "RPMS" / "x86_64" / "vidkonverter-*.rpm"))
    if not built:
        sys.exit("error: rpmbuild reported success but no .rpm was found")

    dist_dir = ROOT / "dist"
    dist_dir.mkdir(exist_ok=True)
    for rpm_path in built:
        dest = dist_dir / Path(rpm_path).name
        shutil.copy2(rpm_path, dest)
        print(f"\nBuilt {dest}")


if __name__ == "__main__":
    main()
