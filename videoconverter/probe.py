"""Wraps ffprobe to extract media file details."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional


class ProbeError(RuntimeError):
    pass


# Pixel formats that carry an alpha plane. Used to decide whether a source
# has transparency that the user might want to preserve or flatten.
ALPHA_PIX_FMTS = {
    "yuva420p", "yuva422p", "yuva444p",
    "yuva420p9le", "yuva420p9be", "yuva422p9le", "yuva422p9be",
    "yuva444p9le", "yuva444p9be",
    "yuva420p10le", "yuva420p10be", "yuva422p10le", "yuva422p10be",
    "yuva444p10le", "yuva444p10be",
    "yuva420p12le", "yuva420p12be", "yuva422p12le", "yuva422p12be",
    "yuva444p12le", "yuva444p12be",
    "yuva420p16le", "yuva420p16be", "yuva422p16le", "yuva422p16be",
    "yuva444p16le", "yuva444p16be",
    "rgba", "bgra", "argb", "abgr",
    "rgba64le", "rgba64be", "bgra64le", "bgra64be",
    "ya8", "ya16le", "ya16be",
    "gbrap", "gbrap10le", "gbrap10be", "gbrap12le", "gbrap12be",
    "gbrap16le", "gbrap16be",
}


@dataclass
class VideoStreamInfo:
    codec_name: str = ""
    codec_long_name: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    pix_fmt: str = ""
    bit_rate: Optional[int] = None

    @property
    def has_alpha(self) -> bool:
        return self.pix_fmt in ALPHA_PIX_FMTS


@dataclass
class AudioStreamInfo:
    codec_name: str = ""
    codec_long_name: str = ""
    sample_rate: int = 0
    channels: int = 0
    channel_layout: str = ""
    bit_rate: Optional[int] = None


@dataclass
class MediaInfo:
    path: str
    format_name: str = ""
    format_long_name: str = ""
    duration_s: float = 0.0
    size_bytes: int = 0
    overall_bit_rate: Optional[int] = None
    video: Optional[VideoStreamInfo] = None
    audio: Optional[AudioStreamInfo] = None
    extra_video_streams: int = 0
    extra_audio_streams: int = 0
    raw: dict = field(default_factory=dict)

    @property
    def has_video(self) -> bool:
        return self.video is not None

    @property
    def has_audio(self) -> bool:
        return self.audio is not None

    @property
    def has_alpha(self) -> bool:
        return bool(self.video and self.video.has_alpha)


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def human_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def human_bitrate(bits_per_sec: Optional[int]) -> str:
    if not bits_per_sec:
        return "unknown"
    kbps = bits_per_sec / 1000.0
    if kbps >= 1000:
        return f"{kbps / 1000.0:.2f} Mbps"
    return f"{kbps:.0f} kbps"


def _parse_fps(rate_str: str) -> float:
    try:
        if "/" in rate_str:
            num, den = rate_str.split("/")
            den = float(den)
            if den == 0:
                return 0.0
            return float(num) / den
        return float(rate_str)
    except (ValueError, ZeroDivisionError):
        return 0.0


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def probe_file(path: str) -> MediaInfo:
    if not ffprobe_available():
        raise ProbeError("ffprobe was not found on your PATH. Please install ffmpeg.")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=30
        )
    except subprocess.CalledProcessError as exc:
        raise ProbeError(f"ffprobe failed: {exc.stderr.strip()}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("ffprobe timed out while reading the file.") from exc

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError("Could not parse ffprobe output.") from exc

    fmt = data.get("format", {})
    info = MediaInfo(path=path, raw=data)
    info.format_name = fmt.get("format_name", "")
    info.format_long_name = fmt.get("format_long_name", "")
    info.duration_s = float(fmt.get("duration", 0.0) or 0.0)
    info.size_bytes = int(fmt.get("size", 0) or 0)
    br = fmt.get("bit_rate")
    info.overall_bit_rate = int(br) if br is not None else None

    for stream in data.get("streams", []):
        codec_type = stream.get("codec_type")
        if codec_type == "video" and info.video is None:
            # Skip embedded cover-art "video" streams (single-frame, no framerate)
            disposition = stream.get("disposition", {})
            if disposition.get("attached_pic"):
                continue
            v = VideoStreamInfo()
            v.codec_name = stream.get("codec_name", "")
            v.codec_long_name = stream.get("codec_long_name", "")
            v.width = int(stream.get("width", 0) or 0)
            v.height = int(stream.get("height", 0) or 0)
            v.fps = _parse_fps(stream.get("r_frame_rate", "0/1"))
            v.pix_fmt = stream.get("pix_fmt", "")
            vb = stream.get("bit_rate")
            v.bit_rate = int(vb) if vb is not None else None
            info.video = v
        elif codec_type == "video":
            info.extra_video_streams += 1
        elif codec_type == "audio" and info.audio is None:
            a = AudioStreamInfo()
            a.codec_name = stream.get("codec_name", "")
            a.codec_long_name = stream.get("codec_long_name", "")
            a.sample_rate = int(stream.get("sample_rate", 0) or 0)
            a.channels = int(stream.get("channels", 0) or 0)
            a.channel_layout = stream.get("channel_layout", "")
            ab = stream.get("bit_rate")
            a.bit_rate = int(ab) if ab is not None else None
            info.audio = a
        elif codec_type == "audio":
            info.extra_audio_streams += 1

    return info


def extract_frame(
    path: str, timestamp_s: float, crop: Optional[tuple] = None
) -> bytes:
    """Extract a single frame as JPEG bytes at the given timestamp,
    optionally cropped to (x, y, w, h) in source-pixel coordinates first."""
    if not ffmpeg_available():
        raise ProbeError("ffmpeg was not found on your PATH. Please install ffmpeg.")

    cmd = ["ffmpeg", "-y", "-ss", f"{max(0.0, timestamp_s):.3f}", "-i", path]
    if crop:
        x, y, w, h = crop
        cmd += ["-vf", f"crop={w}:{h}:{x}:{y}"]
    cmd += ["-frames:v", "1", "-q:v", "3", "-f", "image2pipe", "-vcodec", "mjpeg", "-"]

    try:
        result = subprocess.run(cmd, capture_output=True, check=True, timeout=15)
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.decode(errors="replace").strip()[-300:]
        raise ProbeError(f"ffmpeg failed to extract a preview frame: {message}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("ffmpeg timed out while extracting a preview frame.") from exc

    if not result.stdout:
        raise ProbeError("ffmpeg produced no frame data.")
    return result.stdout
