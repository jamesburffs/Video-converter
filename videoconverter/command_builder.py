"""Translates UI settings into an ffmpeg command line."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

# Container -> (file extension, allowed video codecs, allowed audio codecs)
CONTAINERS = {
    "MP4": {
        "ext": "mp4",
        "video_codecs": ["libx264", "libx265", "copy"],
        "audio_codecs": ["aac", "libmp3lame", "copy"],
        "supports_faststart": True,
    },
    "MOV": {
        "ext": "mov",
        "video_codecs": ["libx264", "libx265", "prores_ks", "copy"],
        "audio_codecs": ["aac", "libmp3lame", "copy"],
        "supports_faststart": True,
    },
    "MKV": {
        "ext": "mkv",
        "video_codecs": ["libx264", "libx265", "libvpx-vp9", "copy"],
        "audio_codecs": ["aac", "libmp3lame", "libopus", "flac", "copy"],
        "supports_faststart": False,
    },
    "WebM": {
        "ext": "webm",
        "video_codecs": ["libvpx-vp9", "copy"],
        "audio_codecs": ["libopus", "copy"],
        "supports_faststart": False,
    },
}

# Codecs where quality is controlled with -crf
CRF_CODECS = {"libx264", "libx265", "libvpx-vp9"}
# Human ffmpeg presets, only meaningful for x264/x265
X264_X265_PRESETS = [
    "ultrafast", "superfast", "veryfast", "faster", "fast",
    "medium", "slow", "slower", "veryslow",
]

VIDEO_CODEC_LABELS = {
    "libx264": "H.264 (libx264)",
    "libx265": "H.265 / HEVC (libx265)",
    "libvpx-vp9": "VP9 (libvpx-vp9)",
    "prores_ks": "Apple ProRes 4444 (prores_ks)",
    "copy": "Copy (no re-encode)",
}

AUDIO_CODEC_LABELS = {
    "aac": "AAC",
    "libmp3lame": "MP3",
    "libopus": "Opus",
    "flac": "FLAC",
    "copy": "Copy (no re-encode)",
}

RESOLUTION_PRESETS = [
    "Source",
    "3840x2160 (4K)",
    "2560x1440 (1440p)",
    "1920x1080 (1080p)",
    "1280x720 (720p)",
    "854x480 (480p)",
    "640x360 (360p)",
    "Custom",
]

# Containers that have an alpha-capable codec available, and which codec
# to use for that container when the user chooses to preserve alpha.
CONTAINER_ALPHA_CODEC = {
    "MOV": "prores_ks",
    "WebM": "libvpx-vp9",
}
ALPHA_CONTAINERS = list(CONTAINER_ALPHA_CODEC.keys())


@dataclass
class ConversionSettings:
    input_path: str
    container: str  # key into CONTAINERS
    video_codec: str
    quality_mode: str  # "crf" or "bitrate"
    # Only meaningful for an actual conversion run (build_command reads it) -
    # optional because ConversionSettings also doubles as the carrier for
    # settings that don't have a real output path yet: extracting a profile
    # to save, or estimating a size before the user has picked one.
    output_path: str = ""
    crf: int = 23
    video_bitrate_kbps: int = 4000
    preset: str = "medium"
    resolution_mode: str = "Source"  # one of RESOLUTION_PRESETS
    custom_width: int = 1920
    custom_height: int = 1080
    keep_aspect: bool = True
    fps_mode: str = "Source"  # "Source" or "Custom"
    custom_fps: float = 30.0
    audio_mode: str = "copy"  # "copy", "encode", "remove"
    audio_codec: str = "aac"
    audio_bitrate_kbps: int = 192
    faststart: bool = False
    # Alpha channel handling
    source_width: int = 0
    source_height: int = 0
    source_has_alpha: bool = False
    alpha_mode: str = "preserve"  # "preserve" or "flatten"
    matte_color: str = "#000000"  # hex, used when alpha_mode == "flatten"
    # Crop, applied (in source pixel coordinates) before any scaling.
    crop_enabled: bool = False
    crop_x: int = 0
    crop_y: int = 0
    crop_w: int = 0
    crop_h: int = 0
    # Trim, in seconds relative to the start of the source file.
    trim_enabled: bool = False
    trim_start_s: float = 0.0
    trim_end_s: float = 0.0


def _resolution_dims(mode: str) -> Optional[tuple]:
    mapping = {
        "3840x2160 (4K)": (3840, 2160),
        "2560x1440 (1440p)": (2560, 1440),
        "1920x1080 (1080p)": (1920, 1080),
        "1280x720 (720p)": (1280, 720),
        "854x480 (480p)": (854, 480),
        "640x360 (360p)": (640, 360),
    }
    return mapping.get(mode)


def _has_crop(s: ConversionSettings) -> bool:
    return s.crop_enabled and s.crop_w > 0 and s.crop_h > 0


def pre_scale_dims(s: ConversionSettings) -> tuple:
    """The frame size entering the scale stage: the crop size if a crop is
    set, otherwise the source size."""
    if _has_crop(s):
        return s.crop_w, s.crop_h
    return s.source_width, s.source_height


def compute_target_dims(s: ConversionSettings) -> Optional[tuple]:
    """Resolve the requested resolution setting to explicit (width, height)
    for the *whole, uncropped* source frame. Returns None if no resolution
    change was requested (resolution_mode == "Source").

    Deliberately independent of any crop: keep-aspect always derives height
    from the source video's own aspect ratio, never the crop's. This is
    also the space crop values are shown/edited in relative to (see
    MainWindow._crop_reference_dims) - a crop is a region of the source, so
    it's shown at whatever size that same region would be if the *entire*
    source frame were scaled to this. crop_scale_dims() below is what
    actually turns that into a scale target once a crop is applied first -
    this function must stay crop-independent for that to mean anything
    (referencing the crop here to decide this would make crop_scale_dims's
    own reference circular)."""
    if s.resolution_mode == "Source":
        return None
    if s.resolution_mode == "Custom":
        w, h = s.custom_width, s.custom_height
    else:
        dims = _resolution_dims(s.resolution_mode)
        if not dims:
            return None
        w, h = dims
    if s.keep_aspect and s.source_width > 0 and s.source_height > 0:
        h = int(round(w * s.source_height / s.source_width))
        if h % 2:
            h += 1
    return w, h


def crop_scale_dims(s: ConversionSettings) -> Optional[tuple]:
    """The (width, height) the scale filter should actually target once a
    crop has already been applied: the crop's own dimensions, scaled by
    the same per-axis ratio the *whole* source frame would be scaled by to
    reach compute_target_dims(). This is the same transform
    MainWindow._scale_rect uses to show/edit crop values against
    compute_target_dims() - so what's displayed always matches what ffmpeg
    actually produces - applied here to size the crop's own output instead.

    Without this, build_command() would scale the cropped region directly
    to compute_target_dims()'s box, which is sized for the *uncropped*
    frame's aspect ratio - stretching non-uniformly whenever the crop's own
    aspect differs from it (e.g. a square crop scaled straight to a 16:9
    target). Returns None if there's no crop, or no resolution change to
    scale the crop against in the first place."""
    if not _has_crop(s):
        return None
    target = compute_target_dims(s)
    if target is None or s.source_width <= 0 or s.source_height <= 0:
        return None
    target_w, target_h = target
    w = int(round(s.crop_w * target_w / s.source_width))
    h = int(round(s.crop_h * target_h / s.source_height))
    if w % 2:
        w += 1
    if h % 2:
        h += 1
    return w, h


def trim_duration_s(s: ConversionSettings) -> Optional[float]:
    """Output duration in seconds once trim is applied, or None if no trim
    is set (or it resolves to an empty/invalid range)."""
    if not s.trim_enabled:
        return None
    d = s.trim_end_s - s.trim_start_s
    return d if d > 0 else None


def effective_duration_s(s: ConversionSettings, source_duration_s: float) -> float:
    """The real output duration: the trimmed length if a trim is set,
    otherwise the source's own duration. Callers that need duration for
    progress reporting or size estimation should use this rather than the
    source duration directly, so a trim is reflected in both."""
    d = trim_duration_s(s)
    return d if d is not None else source_duration_s


def build_command(s: ConversionSettings) -> List[str]:
    video_is_copy = s.video_codec == "copy"
    flatten_alpha = s.source_has_alpha and s.alpha_mode == "flatten" and not video_is_copy
    preserve_alpha = s.source_has_alpha and s.alpha_mode == "preserve" and not video_is_copy

    cmd: List[str] = ["ffmpeg", "-y"]
    # -ss before -i is an input seek: ffmpeg seeks to the nearest preceding
    # keyframe and then decodes/discards forward to the exact requested
    # timestamp, so it's both fast and frame-accurate on re-encode (stream
    # copy is still keyframe-limited, as ffmpeg can't cut mid-GOP without
    # decoding). Output timestamps then restart at 0, so a plain -t
    # (duration, not an absolute -to stop time) below gives exactly the
    # trimmed length regardless of where trim_start_s falls in the source.
    if s.trim_enabled and s.trim_start_s > 0:
        cmd += ["-ss", f"{s.trim_start_s:.3f}"]
    cmd += ["-i", s.input_path]

    target_dims = compute_target_dims(s)
    needs_scale = target_dims is not None
    crop_filter = (
        f"crop={s.crop_w}:{s.crop_h}:{s.crop_x}:{s.crop_y}" if _has_crop(s) else None
    )
    pre_w, pre_h = pre_scale_dims(s)
    # The scale filter (and, for a flattened-alpha composite below, the
    # matte background it's drawn over) needs to target the crop's own
    # scaled size once a crop has already been applied - not target_dims,
    # which is sized for the whole (uncropped) frame's aspect ratio and
    # would stretch a crop whose own aspect differs from it. See
    # crop_scale_dims()'s docstring.
    scale_dims = (crop_scale_dims(s) or target_dims) if needs_scale else None

    if flatten_alpha:
        # Composite the alpha video over a solid matte using a second
        # (color) input, since flattening requires a two-input filter graph.
        w, h = scale_dims if needs_scale else (pre_w or 1920, pre_h or 1080)
        cmd += ["-f", "lavfi", "-i", f"color=c={s.matte_color}:s={w}x{h}"]

    # --- Video ---
    cmd += ["-c:v", s.video_codec]

    if not video_is_copy:
        if s.video_codec in CRF_CODECS:
            if s.quality_mode == "crf":
                cmd += ["-crf", str(s.crf)]
                if s.video_codec == "libvpx-vp9":
                    # VP9 constant-quality mode requires an explicit -b:v 0.
                    cmd += ["-b:v", "0"]
            else:  # bitrate mode
                cmd += ["-b:v", f"{s.video_bitrate_kbps}k"]
        if s.video_codec in ("libx264", "libx265"):
            cmd += ["-preset", s.preset]

        if flatten_alpha:
            w, h = scale_dims if needs_scale else (pre_w or 1920, pre_h or 1080)
            fg_filters = []
            if crop_filter:
                fg_filters.append(crop_filter)
            fg_filters.append(f"scale={w}:{h}")
            filter_complex = (
                f"[0:v]{','.join(fg_filters)}[fg];[1:v][fg]overlay=shortest=1[outv]"
            )
            cmd += ["-filter_complex", filter_complex, "-map", "[outv]"]
            if s.audio_mode != "remove":
                cmd += ["-map", "0:a?"]
        else:
            vf_filters = []
            if crop_filter:
                vf_filters.append(crop_filter)
            if needs_scale:
                w, h = scale_dims
                vf_filters.append(f"scale={w}:{h}")
            if vf_filters:
                cmd += ["-vf", ",".join(vf_filters)]

        if s.fps_mode == "Custom":
            cmd += ["-r", str(s.custom_fps)]

        if preserve_alpha:
            if s.video_codec == "prores_ks":
                cmd += ["-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
            elif s.video_codec == "libvpx-vp9":
                cmd += ["-pix_fmt", "yuva420p", "-auto-alt-ref", "0"]
    else:
        # Stream copy is incompatible with filters/scaling.
        pass

    # --- Audio ---
    if s.audio_mode == "remove":
        cmd += ["-an"]
    elif s.audio_mode == "copy":
        cmd += ["-c:a", "copy"]
    else:  # encode
        cmd += ["-c:a", s.audio_codec]
        if s.audio_codec != "copy":
            cmd += ["-b:a", f"{s.audio_bitrate_kbps}k"]

    duration = trim_duration_s(s)
    if duration is not None:
        cmd += ["-t", f"{duration:.3f}"]

    # --- Container-specific flags ---
    container_info = CONTAINERS.get(s.container, {})
    if s.faststart and container_info.get("supports_faststart"):
        cmd += ["-movflags", "+faststart"]

    cmd += ["-progress", "pipe:1", "-nostats"]
    cmd += [s.output_path]
    return cmd


# Rough bits-per-pixel-per-frame at CRF 23, used only to ballpark an output
# size for CRF-mode encodes. Real output size depends heavily on content
# complexity, so this is a rule-of-thumb (CRF+6 ~= half the bitrate),
# not a real estimate.
_BASELINE_BPP_AT_CRF23 = {
    "libx264": 0.08,
    "libx265": 0.045,
    "libvpx-vp9": 0.045,
}
_BASELINE_CRF = 23
_FALLBACK_AUDIO_BIT_RATE = 128_000


def estimate_output_size_bytes(
    s: ConversionSettings,
    duration_s: float,
    source_fps: float = 30.0,
    source_size_bytes: int = 0,
    source_audio_bit_rate: Optional[int] = None,
    source_has_audio: bool = True,
) -> Optional[int]:
    """Ballpark the output file size in bytes, or None if it can't be
    reasonably estimated (e.g. ProRes, whose rate isn't user-controlled here).
    """
    if duration_s <= 0:
        return None

    video_is_copy = s.video_codec == "copy"
    audio_is_copy = s.audio_mode == "copy"

    if video_is_copy and audio_is_copy:
        return source_size_bytes or None

    # --- Video bits ---
    video_bits: Optional[float]
    if video_is_copy:
        video_bits = None  # unknown without the source's video-only bitrate
    elif s.video_codec in CRF_CODECS:
        if s.quality_mode == "bitrate":
            video_bits = s.video_bitrate_kbps * 1000 * duration_s
        else:
            dims = crop_scale_dims(s) or compute_target_dims(s) or pre_scale_dims(s)
            w, h = dims
            if not w or not h:
                return None
            fps = s.custom_fps if s.fps_mode == "Custom" else (source_fps or 30.0)
            baseline = _BASELINE_BPP_AT_CRF23.get(s.video_codec, 0.08)
            bpp = baseline * (2 ** ((_BASELINE_CRF - s.crf) / 6.0))
            video_bits = bpp * w * h * fps * duration_s
    else:
        return None  # e.g. ProRes: rate isn't controlled by this UI

    if video_bits is None:
        return None

    # --- Audio bits ---
    if s.audio_mode == "remove" or not source_has_audio:
        audio_bits = 0.0
    elif s.audio_mode == "encode":
        audio_bits = s.audio_bitrate_kbps * 1000 * duration_s
    else:  # copy
        audio_bits = (source_audio_bit_rate or _FALLBACK_AUDIO_BIT_RATE) * duration_s

    return int((video_bits + audio_bits) / 8)


def command_to_display_string(cmd: List[str]) -> str:
    """Quote args that contain spaces for a readable, copy-pasteable preview."""
    parts = []
    for arg in cmd:
        if " " in arg or arg == "":
            parts.append(f'"{arg}"')
        else:
            parts.append(arg)
    return " ".join(parts)
