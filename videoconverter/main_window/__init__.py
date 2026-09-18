"""MainWindow, split by concern into one mixin file per topic so it's easier
to find things without reading one huge class:

    base.py                  - composition root: __init__, top-level UI
                                assembly, signal wiring, window lifecycle
    source_mixin.py           - source selection (single file + batch folder),
                                file info display, batch scan/queue table
    profiles_mixin.py         - save/load/update/delete settings profiles
    codec_container_mixin.py  - container/codec/quality/fps page
    audio_mixin.py             - audio track page
    crop_mixin.py              - size/crop page (+ the small trim-state
                                methods, since trim is a view onto crop
                                state rather than a page of its own)
    alpha_mixin.py             - alpha-channel handling
    output_preview_mixin.py    - command preview page, settings gathering,
                                size estimate
    conversion_mixin.py        - convert/cancel, progress dialog, single and
                                batch conversion execution

All mixins share one `self` at runtime (MainWindow inherits every one of
them - see base.py), so a method in any file can freely call
self.<anything defined in any other mixin> exactly as it could when this
was all one class. The split only changes where to go looking for
something, not how any of it behaves.
"""
from .base import MainWindow

__all__ = ["MainWindow"]
