"""Detects a safe, platform-appropriate way to install ffmpeg."""
from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass
from typing import List, Optional

FFMPEG_DOWNLOAD_PAGE = "https://ffmpeg.org/download.html"
HOMEBREW_PAGE = "https://brew.sh"


@dataclass
class InstallPlan:
    description: str
    # A ready-to-run argv that installs ffmpeg, or None if no safe automated
    # path was found (caller should fall back to manual instructions).
    command: Optional[List[str]] = None
    manual_instructions: str = ""
    # Page to send the user to for a manual install. Defaults to the ffmpeg
    # downloads page, but e.g. macOS without Homebrew points at brew.sh
    # instead, since that's what the manual instructions actually tell them
    # to do.
    download_url: str = FFMPEG_DOWNLOAD_PAGE
    download_label: str = "Open Download Page"


def _linux_plan() -> InstallPlan:
    # (binary to detect, install argv, human label)
    managers = [
        ("apt-get", ["apt-get", "install", "-y", "ffmpeg"], "apt"),
        ("dnf", ["dnf", "install", "-y", "ffmpeg"], "dnf"),
        ("yum", ["yum", "install", "-y", "ffmpeg"], "yum"),
        ("pacman", ["pacman", "-S", "--noconfirm", "ffmpeg"], "pacman"),
        ("zypper", ["zypper", "install", "-y", "ffmpeg"], "zypper"),
        ("apk", ["apk", "add", "ffmpeg"], "apk"),
    ]
    for binary, cmd, label in managers:
        if not shutil.which(binary):
            continue
        pkexec = shutil.which("pkexec")
        if pkexec:
            return InstallPlan(
                description=f"Install ffmpeg via {label} (you'll be asked for your password).",
                command=[pkexec] + cmd,
            )
        return InstallPlan(
            description=f"Detected {label}, but no graphical privilege helper (pkexec) is available.",
            manual_instructions=f"Open a terminal and run:\n  sudo {' '.join(cmd)}",
        )
    return InstallPlan(
        description="Could not detect a supported package manager.",
        manual_instructions="Install ffmpeg using your distribution's package manager.",
    )


def _macos_plan() -> InstallPlan:
    if shutil.which("brew"):
        return InstallPlan(
            description="Install ffmpeg via Homebrew.",
            command=["brew", "install", "ffmpeg"],
        )
    return InstallPlan(
        description="Homebrew was not found.",
        manual_instructions=(
            "Install Homebrew from https://brew.sh, then run:\n  brew install ffmpeg"
        ),
        download_url=HOMEBREW_PAGE,
        download_label="Open Homebrew Website",
    )


def _windows_plan() -> InstallPlan:
    if shutil.which("winget"):
        return InstallPlan(
            description="Install ffmpeg via winget.",
            command=[
                "winget", "install", "-e", "--id", "Gyan.FFmpeg",
                "--accept-source-agreements", "--accept-package-agreements",
            ],
        )
    if shutil.which("choco"):
        return InstallPlan(
            description="Install ffmpeg via Chocolatey.",
            command=["choco", "install", "-y", "ffmpeg"],
        )
    return InstallPlan(
        description="No supported package manager (winget/choco) was found.",
        manual_instructions=(
            "Download a Windows build from the official ffmpeg downloads page "
            "and add its bin folder to your PATH."
        ),
    )


def detect_install_plan() -> InstallPlan:
    system = platform.system()
    if system == "Linux":
        return _linux_plan()
    if system == "Darwin":
        return _macos_plan()
    if system == "Windows":
        return _windows_plan()
    return InstallPlan(
        description="Unsupported platform.",
        manual_instructions="Please install ffmpeg manually.",
    )
