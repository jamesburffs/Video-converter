"""Environment for launching *external* processes (ffmpeg, ffprobe, a
system package manager) - anything this app doesn't bundle itself.

PyInstaller's Linux/macOS bootloader points LD_LIBRARY_PATH/DYLD_LIBRARY_PATH
at its own bundled libs directory, for its own frozen process to resolve its
dependencies against consistently. A subprocess inherits that by default,
which breaks any *external*, non-bundled binary the app spawns if the
bundle happens to carry an older build of a library the system binary also
needs - this genuinely broke ffprobe's own libcurl/OpenSSL dependency in
practice (the bundle's libssl.so.3 too old for the system libcurl.so.4).

PyInstaller documents this exact problem and its fix: it saves the
original, pre-hijack value under a "_ORIG"-suffixed variable specifically
so it can be restored for a subprocess that should see the real system
environment instead - see
https://pyinstaller.org/en/stable/runtime-information.html#ld-library-path-libpath-considerations
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QProcessEnvironment

_LIB_PATH_VARS = ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH")


def external_process_env() -> dict:
    """A copy of the current environment with PyInstaller's library-path
    injection undone (a no-op when not running frozen, or on Windows) -
    pass as `env=` to subprocess.run/Popen, or via QProcessEnvironment,
    whenever launching a binary that isn't part of this app's own bundle.

    PyInstaller's "_ORIG" backup only exists at all if the var had a value
    *before* it was overridden - for the common case of a user who's never
    set LD_LIBRARY_PATH themselves, there's nothing to back up, so no
    backup key is created, even though the var absolutely is still set (to
    the bootloader's extraction dir) for this frozen process. Gating the
    restoration on "does a backup key exist" - rather than treating a
    missing backup as "remove the var, there was nothing here before" per
    PyInstaller's own documented recipe - left that extraction dir in
    place for exactly this, the most common, case: confirmed via a real
    crash report where ffprobe's system libcurl resolved the bundle's own
    (older) libssl.so.3 instead of the system's."""
    env = dict(os.environ)
    if not getattr(sys, "frozen", False):
        return env
    for var in _LIB_PATH_VARS:
        orig = env.pop(f"{var}_ORIG", None)
        if orig:
            env[var] = orig
        else:
            env.pop(var, None)
    return env


def clean_qprocess_environment() -> QProcessEnvironment:
    """external_process_env(), as a QProcessEnvironment for QProcess.
    setProcessEnvironment() - used instead of subprocess for a process that
    needs to stream output live (ffmpeg during a real conversion, or a
    package manager's install command) rather than just run to completion."""
    qenv = QProcessEnvironment()
    for key, value in external_process_env().items():
        qenv.insert(key, value)
    return qenv


_MACOS_HOMEBREW_BIN_DIRS = ("/opt/homebrew/bin", "/usr/local/bin")


def ensure_macos_homebrew_on_path() -> None:
    """Homebrew installs to /opt/homebrew/bin (Apple Silicon) or
    /usr/local/bin (Intel Macs), and adds that to PATH via a line its own
    installer puts in the user's shell profile (`eval "$(brew shellenv)"`)
    - which only takes effect for processes launched *from* that shell.
    An app launched by double-clicking it (or via Spotlight, the Dock,
    etc.) is started by launchd instead, with its own minimal default
    PATH that never goes through the user's shell startup at all - so
    ffmpeg/ffprobe, and this app's own "Install FFmpeg" button (which
    needs to find `brew` itself first), can be genuinely installed and
    working fine from Terminal while this app still can't find either.

    Patching PATH itself, once, here - rather than resolving each binary
    individually at each call site - fixes every shutil.which()/
    subprocess/QProcess call that follows, since they all inherit this
    process's environment (or a copy of it - see external_process_env()
    above) from this point on. Call once at startup, before any ffmpeg/
    ffprobe/brew detection or invocation; a no-op on every other
    platform."""
    if sys.platform != "darwin":
        return
    existing = os.environ.get("PATH", "")
    parts = existing.split(os.pathsep) if existing else []
    for bin_dir in _MACOS_HOMEBREW_BIN_DIRS:
        if os.path.isdir(bin_dir) and bin_dir not in parts:
            parts.append(bin_dir)
    os.environ["PATH"] = os.pathsep.join(parts)


def _windows_registry_path() -> str:
    """The current machine + user PATH as stored in the registry - unlike
    this process's own environment, this reflects installs made since the
    app started."""
    import winreg
    parts = []
    for hive, subkey in (
        (winreg.HKEY_LOCAL_MACHINE,
         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, "Environment"),
    ):
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
                parts.append(os.path.expandvars(value))
        except OSError:
            pass
    return ";".join(p for p in parts if p)


def restart_application() -> bool:
    """Launch a fresh copy of this app, detached, so it picks up a PATH
    changed since startup. The caller should quit afterwards."""
    from PySide6.QtCore import QProcess

    env = QProcessEnvironment.systemEnvironment()
    if sys.platform == "win32":
        fresh = _windows_registry_path()
        if fresh:
            env.insert("PATH", fresh)
    # A one-file PyInstaller child must extract its own bundle rather than
    # reuse the parent's temp dir, which vanishes when the parent exits.
    env.insert("PYINSTALLER_RESET_ENVIRONMENT", "1")

    args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
    proc = QProcess()
    proc.setProgram(sys.executable)
    proc.setArguments(args)
    proc.setProcessEnvironment(env)
    started, _pid = proc.startDetached()
    return started
