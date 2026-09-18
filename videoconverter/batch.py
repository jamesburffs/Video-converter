"""Folder scanning and queue management for batch conversion."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set

from . import probe

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv", ".flv",
    ".mpg", ".mpeg", ".ts", ".m2ts", ".mts", ".3gp", ".ogv", ".vob",
}


class ItemStatus(Enum):
    PENDING = "Pending"
    UNREADABLE = "Could not read"
    CONVERTING = "Converting"
    DONE = "Done"
    FAILED = "Failed"


@dataclass
class BatchItem:
    input_path: str
    media_info: Optional[probe.MediaInfo] = None
    output_path: str = ""
    status: ItemStatus = ItemStatus.PENDING
    error: str = ""


def find_video_files(folder: str, recursive: bool) -> List[str]:
    results = []
    if recursive:
        for root, _dirs, files in os.walk(folder):
            for name in files:
                if os.path.splitext(name)[1].lower() in VIDEO_EXTENSIONS:
                    results.append(os.path.join(root, name))
    else:
        for name in sorted(os.listdir(folder)):
            full = os.path.join(folder, name)
            if os.path.isfile(full) and os.path.splitext(name)[1].lower() in VIDEO_EXTENSIONS:
                results.append(full)
    results.sort()
    return results


def probe_one(path: str) -> BatchItem:
    item = BatchItem(input_path=path)
    try:
        item.media_info = probe.probe_file(path)
    except probe.ProbeError as exc:
        item.status = ItemStatus.UNREADABLE
        item.error = str(exc)
    return item


def summarize(items: List[BatchItem]) -> str:
    total = len(items)
    ok = [i for i in items if i.media_info is not None]
    unreadable = total - len(ok)
    total_size = sum(i.media_info.size_bytes for i in ok)
    total_duration = sum(i.media_info.duration_s for i in ok)

    codec_counts = {}
    alpha_count = 0
    for i in ok:
        if i.media_info.video:
            name = i.media_info.video.codec_name or "unknown"
            codec_counts[name] = codec_counts.get(name, 0) + 1
            if i.media_info.video.has_alpha:
                alpha_count += 1

    lines = [f"{total} video file(s) found"]
    if unreadable:
        lines.append(f"{unreadable} file(s) could not be read and will be skipped")
    lines.append(f"Total size: {probe.human_size(total_size)}")
    lines.append(f"Total duration: {probe.human_duration(total_duration)}")
    if codec_counts:
        codecs_str = ", ".join(
            f"{k} x{v}" for k, v in sorted(codec_counts.items(), key=lambda kv: -kv[1])
        )
        lines.append(f"Video codecs: {codecs_str}")
    if alpha_count:
        lines.append(f"{alpha_count} file(s) contain an alpha channel")
    return "\n".join(lines)


def _unique_path(path: str, taken: Set[str]) -> str:
    if path not in taken:
        taken.add(path)
        return path
    base, ext = os.path.splitext(path)
    n = 2
    while True:
        candidate = f"{base}_{n}{ext}"
        if candidate not in taken:
            taken.add(candidate)
            return candidate
        n += 1


def assign_output_paths(items: List[BatchItem], dest_folder: str, ext: str) -> None:
    taken: Set[str] = set()
    for item in items:
        if item.media_info is None:
            continue
        base = os.path.splitext(os.path.basename(item.input_path))[0]
        candidate = os.path.join(dest_folder, f"{base}.{ext}")
        item.output_path = _unique_path(candidate, taken)
