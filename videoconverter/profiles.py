"""Save/load named output-setting profiles to a per-user config directory."""
from __future__ import annotations

import json
import os
import shutil
from typing import List

from PySide6.QtCore import QStandardPaths

from .command_builder import ConversionSettings

# QStandardPaths.AppConfigLocation is derived from QApplication's
# applicationName ("VidKonverter" - see __main__.py), which used to be
# "Video Converter". Without migrating, renaming the app would silently
# strand any profiles saved under the old name.
_OLD_APP_NAME = "Video Converter"

# Fields worth persisting as part of a reusable profile - everything except
# the per-run input/output paths and per-source dimension info, which depend
# on whatever file the profile is later applied to. Crop coordinates are
# saved too (in absolute source-pixel terms); whoever applies the profile
# clamps them to fit that file's actual dimensions.
PROFILE_FIELDS = [
    "container", "video_codec", "quality_mode", "crf", "video_bitrate_kbps",
    "preset", "resolution_mode", "custom_width", "custom_height", "keep_aspect",
    "fps_mode", "custom_fps", "audio_mode", "audio_codec", "audio_bitrate_kbps",
    "faststart", "alpha_mode", "matte_color",
    "crop_enabled", "crop_x", "crop_y", "crop_w", "crop_h",
]


def _migrate_old_config_dir(new_base: str) -> None:
    """One-time move of the old "Video Converter"-named config directory to
    the new app-name-derived one, so the rename doesn't orphan profiles
    someone already saved."""
    if os.path.isdir(new_base):
        return
    generic_config = QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation)
    if not generic_config:
        return
    old_base = os.path.join(generic_config, _OLD_APP_NAME)
    if os.path.isdir(old_base):
        os.makedirs(os.path.dirname(new_base), exist_ok=True)
        shutil.move(old_base, new_base)


def _profiles_dir() -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".config", "VidKonverter")
    _migrate_old_config_dir(base)
    path = os.path.join(base, "profiles")
    os.makedirs(path, exist_ok=True)
    return path


def safe_name(name: str) -> str:
    keep = "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()
    return keep or "profile"


def list_profiles() -> List[str]:
    d = _profiles_dir()
    return sorted(
        fname[:-5] for fname in os.listdir(d) if fname.endswith(".json")
    )


def save_profile(name: str, settings: ConversionSettings) -> str:
    name = safe_name(name)
    data = {field: getattr(settings, field) for field in PROFILE_FIELDS}
    path = os.path.join(_profiles_dir(), f"{name}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return name


def load_profile(name: str) -> dict:
    path = os.path.join(_profiles_dir(), f"{safe_name(name)}.json")
    with open(path) as f:
        return json.load(f)


def delete_profile(name: str) -> None:
    path = os.path.join(_profiles_dir(), f"{safe_name(name)}.json")
    if os.path.exists(path):
        os.remove(path)
