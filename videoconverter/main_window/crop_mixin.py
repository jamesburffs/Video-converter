"""Size/Crop page: resolution + crop controls, the crop preview and its
scrubber, and the small trim-state methods (trim is a view onto the crop
rect via TrimPanel, not a page of its own - see trim_panel.py)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from .. import probe
from ..command_builder import RESOLUTION_PRESETS, compute_target_dims
from ..crop_dialog import CropDialog
from ..crop_overlay import draw_crop_mask
from ..widgets import NoWheelSlider

# How long after the crop preview scrubber last moved to actually extract
# and show the new frame - see _on_crop_scrub_moved.
_CROP_SCRUB_DEBOUNCE_MS = 150


class _ScaledPreviewLabel(QLabel):
    """A QLabel that keeps a source QPixmap fitted (preserving aspect ratio)
    to the label's current size as it's resized, instead of showing the
    image at its native resolution."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._source_pixmap: QPixmap | None = None
        # A plain QLabel's sizeHint() (and so its actual allocated size,
        # under the default Preferred policy) tracks whatever pixmap is
        # currently set - so setting a smaller/narrower-aspect preview would
        # shrink the label itself on the next relayout, compounding on every
        # crop change instead of the box staying put while just the shown
        # aspect changes within it. A fixed height + horizontally-expanding
        # policy makes the box's size independent of its content.
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_source_pixmap(self, pixmap: QPixmap | None):
        self._source_pixmap = pixmap
        self._rescale()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self):
        if self._source_pixmap is None or self._source_pixmap.isNull():
            return
        self.setPixmap(self._source_pixmap.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))


class CropMixin:
    def _build_size_crop_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)

        # A crop/resolution setting is a single absolute-pixel rectangle
        # (or target size) applied uniformly across every file in a batch -
        # meaningless if they're not all the same frame size to begin with.
        # See _update_crop_controls_enabled, which toggles this in place of
        # the controls below rather than leaving them to silently produce
        # nonsensical per-file results.
        self.crop_unavailable_label = QLabel(
            "Size and cropping features are only available when all source "
            "videos are the same frame size."
        )
        self.crop_unavailable_label.setWordWrap(True)
        self.crop_unavailable_label.setStyleSheet("color: gray;")
        self.crop_unavailable_label.setVisible(False)
        page_layout.addWidget(self.crop_unavailable_label)

        self.crop_controls_widget = QWidget()
        controls_layout = QVBoxLayout(self.crop_controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self.crop_controls_widget)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        # Resolution
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(RESOLUTION_PRESETS)
        form.addRow("Resolution:", self.resolution_combo)

        custom_res_row = QHBoxLayout()
        self.custom_width_spin = QSpinBox()
        self.custom_width_spin.setRange(2, 16384)
        self.custom_width_spin.setValue(1920)
        self.custom_height_spin = QSpinBox()
        self.custom_height_spin.setRange(2, 16384)
        self.custom_height_spin.setValue(1080)
        self.keep_aspect_check = QCheckBox("Keep aspect ratio (derive height)")
        self.keep_aspect_check.setChecked(True)
        custom_res_row.addWidget(QLabel("W:"))
        custom_res_row.addWidget(self.custom_width_spin)
        custom_res_row.addWidget(QLabel("H:"))
        custom_res_row.addWidget(self.custom_height_spin)
        custom_res_row.addWidget(self.keep_aspect_check)
        self.custom_res_row_widget = QWidget()
        self.custom_res_row_widget.setLayout(custom_res_row)
        form.addRow("Custom size:", self.custom_res_row_widget)

        # Crop
        crop_row = QHBoxLayout()
        self.set_crop_button = QPushButton("Set Crop…")
        self.reset_crop_button = QPushButton("Reset")
        self.reset_crop_button.setEnabled(False)
        self.crop_status_label = QLabel("Full frame")
        self.crop_status_label.setStyleSheet("color: gray;")
        crop_row.addWidget(self.set_crop_button)
        crop_row.addWidget(self.reset_crop_button)
        crop_row.addWidget(self.crop_status_label, stretch=1)
        form.addRow("Crop:", crop_row)

        controls_layout.addLayout(form)

        controls_layout.addWidget(self._section_heading("Preview"))
        self.crop_preview_label = _ScaledPreviewLabel("No preview available")
        self.crop_preview_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.crop_preview_label.setFixedHeight(160)
        self.crop_preview_label.setStyleSheet("QLabel { color: gray; }")
        controls_layout.addWidget(self.crop_preview_label)

        # Lets the user scrub through the source themselves to check the
        # crop at a different point in the video, without leaving this page
        # for the (much heavier) crop dialog. Only meaningful - so only
        # visible - once a crop is actually set (see _refresh_crop_preview,
        # which also keeps its width matched to the preview image's own
        # rendered width, not the page's).
        self.crop_scrub_slider = NoWheelSlider(Qt.Horizontal)
        self.crop_scrub_slider.setVisible(False)
        controls_layout.addWidget(self.crop_scrub_slider, alignment=Qt.AlignLeft)

        page_layout.addStretch(1)
        return page

    def _update_computed_height(self, *_):
        if self.keep_aspect_check.isChecked():
            # Aspect is derived from the source frame only, independent of
            # any crop - matches compute_target_dims() in command_builder,
            # which the actual ffmpeg command uses. Resolution and crop are
            # decoupled: a crop must never feed back into this (see
            # compute_target_dims()'s docstring - crop_scale_dims() is what
            # actually accounts for an active crop, applied only once
            # building the real ffmpeg command).
            dims = self._current_source_dims()
            if dims and dims[0] > 0:
                sw, sh = dims
                w = self.custom_width_spin.value()
                h = int(round(w * sh / sw))
                if h % 2:
                    h += 1
                if self.custom_height_spin.value() != h:
                    self.custom_height_spin.blockSignals(True)
                    self.custom_height_spin.setValue(h)
                    self.custom_height_spin.blockSignals(False)
        # The target resolution (and therefore the space crop values are
        # displayed in) may have just changed - refresh the crop status
        # label so it stays proportional to whatever was selected.
        self._update_crop_status()

    def _current_crop_reference(self):
        """(path, width, height) of the video to preview/crop against, or
        None if there's nothing loaded yet to determine dimensions from."""
        info = self._current_media_info()
        return (info.path, info.video.width, info.video.height) if info else None

    def _current_crop_media_info(self) -> probe.MediaInfo | None:
        """The MediaInfo backing _current_crop_reference(), for details (like
        duration) that reference alone doesn't carry."""
        return self._current_media_info()

    def _on_crop_scrub_moved(self, _value: int):
        self._crop_scrub_timer.start()

    def _refresh_crop_preview(self):
        """Show the *whole* source frame at its own native aspect ratio,
        darkened everywhere except the active crop (see draw_crop_mask in
        crop_overlay) - showing where the crop sits against the full
        picture, rather than just the cropped-out result on its own (which
        would also change aspect ratio with every crop edit, unlike the
        full frame's, so the scrubber below couldn't stay a stable width
        against it either). Only shown - and the scrubber only visible -
        once a crop is actually set: with no crop there's nothing to
        darken, and a plain frame doesn't reflect the chosen
        resolution/scale setting at all (see crop_scale_dims in
        command_builder), so there's nothing meaningfully previewable
        without one. Switching to a different source resets the scrubber
        to a sensible starting point; adjusting the crop (or just
        scrubbing) on the same file leaves it where it was."""
        ref = self._current_crop_reference()
        if not ref:
            self._crop_preview_path = None
            self.crop_scrub_slider.setVisible(False)
            self.crop_preview_label.set_source_pixmap(None)
            self.crop_preview_label.setText("No preview available")
            return
        path, source_w, source_h = ref

        info = self._current_crop_media_info()
        duration = info.duration_s if info else 0.0

        if path != self._crop_preview_path:
            self._crop_preview_path = path
            # Skip the very start - more likely to be black or a fade than
            # something representative of the actual crop.
            start_s = min(duration * 0.1, duration) if duration > 1.0 else 0.0
            self.crop_scrub_slider.blockSignals(True)
            self.crop_scrub_slider.setRange(0, max(0, int(duration * 1000)))
            self.crop_scrub_slider.setValue(int(start_s * 1000))
            self.crop_scrub_slider.blockSignals(False)

        if self._crop_rect is None:
            self.crop_scrub_slider.setVisible(False)
            self.crop_preview_label.set_source_pixmap(None)
            self.crop_preview_label.setText("Preview available once a crop is set.")
            return

        timestamp = self.crop_scrub_slider.value() / 1000.0

        self.crop_preview_label.set_source_pixmap(None)
        self.crop_preview_label.setText("Generating preview…")
        QApplication.processEvents()
        try:
            data = probe.extract_frame(path, timestamp)
        except probe.ProbeError:
            self.crop_scrub_slider.setVisible(False)
            self.crop_preview_label.setText("Preview unavailable")
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data) or pixmap.isNull():
            self.crop_scrub_slider.setVisible(False)
            self.crop_preview_label.setText("Preview unavailable")
            return

        x = min(self._crop_rect.x(), source_w - 1)
        y = min(self._crop_rect.y(), source_h - 1)
        w = min(self._crop_rect.width(), source_w - x)
        h = min(self._crop_rect.height(), source_h - y)
        painter = QPainter(pixmap)
        draw_crop_mask(
            painter, QRectF(0, 0, pixmap.width(), pixmap.height()),
            QRectF(x, y, w, h), QColor(0, 0, 0, 170),
        )
        painter.end()

        self.crop_preview_label.setText("")
        self.crop_preview_label.set_source_pixmap(pixmap)

        # The scrubber is only ever as wide as the preview image actually
        # renders at (letterboxed within crop_preview_label's fixed
        # height, left-aligned) - not the much wider page it sits in.
        label_h = self.crop_preview_label.height()
        if label_h > 0 and pixmap.height() > 0:
            rendered_w = max(1, int(label_h * pixmap.width() / pixmap.height()))
            self.crop_scrub_slider.setFixedWidth(rendered_w)
        self.crop_scrub_slider.setVisible(True)

    def _batch_video_dims_consistent(self) -> bool:
        """Whether every scanned batch item with a probed video stream
        shares the same frame size. A crop rect (or a resolution target,
        for that matter) is one absolute-pixel setting applied uniformly
        to every file in the batch - if the source files aren't all the
        same size, that setting doesn't mean the same thing for each of
        them, so Size/Crop is hidden entirely rather than left to produce
        confusing, inconsistent-looking results per file."""
        dims = {
            (i.media_info.video.width, i.media_info.video.height)
            for i in self.batch_items if i.media_info and i.media_info.video
        }
        return len(dims) <= 1

    def _update_crop_controls_enabled(self):
        available = not self._is_batch_mode() or self._batch_video_dims_consistent()
        self.crop_controls_widget.setVisible(available)
        self.crop_unavailable_label.setVisible(not available)

        can_crop = (
            available
            and self._current_crop_reference() is not None
            and self._current_video_codec() != "copy"
        )
        self.set_crop_button.setEnabled(can_crop)

    def _crop_reference_dims(self):
        """(width, height) of the coordinate space crop status/values are
        shown and edited in: the selected output resolution once the user
        has chosen one, otherwise the source video's own dimensions.
        self._crop_rect is always stored in source-pixel terms (that's what
        ffmpeg's crop filter needs, applied before any scaling) - this is
        purely the display/edit space, recomputed fresh each time so the
        numbers stay meaningful as the resolution setting changes, without
        ever mutating the stored crop itself.

        This is one-directional and matches compute_target_dims() in
        command_builder (which the real ffmpeg command uses) exactly:
        resolution is computed independent of any crop, and crop is shown
        relative to whatever that resolves to - never the other way around.
        A crop shown/edited this way (rather than in raw source pixels)
        is what actually stays visually consistent once ffmpeg scales the
        crop to match (see command_builder.crop_scale_dims): the region you
        draw is the same region ffmpeg keeps, just expressed at whatever
        size the whole frame would be at this resolution. When no scale
        filter ends up applied at all (resolution mode "Source", or a
        "copy" codec), that "whatever" is just the source's own
        dimensions, unscaled - not the crop's, which would make this
        self-referential (crop shown relative to crop) the same way
        compute_target_dims() must not reference the crop for aspect."""
        ref = self._current_crop_reference()
        if not ref:
            return None
        _, source_w, source_h = ref
        if self._current_video_codec() == "copy":
            return source_w, source_h
        target = compute_target_dims(self._gather_settings())
        if target and target[0] > 0 and target[1] > 0:
            return target
        return source_w, source_h

    @staticmethod
    def _scale_rect(r: QRect, from_dims, to_dims) -> QRect:
        fw, fh = from_dims
        tw, th = to_dims
        if fw <= 0 or fh <= 0:
            return QRect(r)
        sx = tw / fw
        sy = th / fh
        return QRect(
            round(r.x() * sx), round(r.y() * sy),
            max(1, round(r.width() * sx)), max(1, round(r.height() * sy)),
        )

    def _update_crop_status(self):
        ref = self._current_crop_reference()
        is_full = self._crop_rect is not None and ref is not None and (
            self._crop_rect.x() == 0 and self._crop_rect.y() == 0
            and self._crop_rect.width() == ref[1] and self._crop_rect.height() == ref[2]
        )
        if self._crop_rect is None or is_full:
            self._crop_rect = None
            self.crop_status_label.setText("Full frame")
            self.reset_crop_button.setEnabled(False)
            return
        r = self._crop_rect
        if ref:
            ref_dims = self._crop_reference_dims()
            if ref_dims:
                # Scale as if the *whole* source frame were resized to the
                # resolution setting's pixel grid (matching whatever
                # scale=w:h the real command will run - possibly non-uniform
                # if the crop's aspect differs from the chosen resolution's,
                # in which case the crop genuinely will be stretched to fill
                # it) and see where the crop lands in that space.
                r = self._scale_rect(r, (ref[1], ref[2]), ref_dims)
        self.crop_status_label.setText(f"{r.width()}x{r.height()} @ ({r.x()}, {r.y()})")
        self.reset_crop_button.setEnabled(True)

    def _on_set_crop_clicked(self):
        ref = self._current_crop_reference()
        if not ref:
            return
        path, source_w, source_h = ref
        # The resolution setting alone determines this - a crop being active
        # doesn't change it (see _crop_reference_dims), so the same canvas
        # is used whether drawing a fresh crop or adjusting an existing one.
        w, h = self._crop_reference_dims() or (source_w, source_h)
        initial = (
            self._scale_rect(self._crop_rect, (source_w, source_h), (w, h))
            if self._crop_rect is not None else None
        )
        dialog = CropDialog(path, w, h, initial_crop=initial, parent=self)
        if dialog.exec() == QDialog.Accepted and dialog.result_crop:
            self._crop_rect = self._scale_rect(dialog.result_crop, (w, h), (source_w, source_h))
            # The resolution setting is never touched by a crop change - only
            # the crop's own state (and, via keep-aspect, the computed
            # height, which is itself source-aspect-only - see
            # _update_computed_height) responds to it.
            self._update_crop_status()
            self._update_computed_height()
            self._refresh_crop_preview()
            self._update_trim_crop_view()
            self._rebuild_command_preview()

    def _on_reset_crop_clicked(self):
        self._crop_rect = None
        self._update_crop_status()
        self._update_computed_height()
        self._refresh_crop_preview()
        self._update_trim_crop_view()
        self._rebuild_command_preview()

    # ------------------------------------------------------------------
    # Trim
    # ------------------------------------------------------------------
    def _refresh_trim_source(self):
        """Point the Trim page's preview at the current source (or clear
        it) - mirrors what a newly opened crop dialog does, but inline
        since Trim is always visible as a nav page rather than a modal.
        Trim is single-file-only (see _update_trim_nav_enabled), so the
        controls stay inert in batch mode too, as a fallback in case the
        page is still showing when the mode switches."""
        info = self._current_crop_media_info()
        has_video = bool(info and info.video) and not self._is_batch_mode()
        self.trim_panel.set_source(info, has_video)
        if has_video:
            self.trim_panel.set_crop(self._crop_rect)

    def _update_trim_crop_view(self):
        self.trim_panel.set_crop(self._crop_rect)

    def _update_trim_nav_enabled(self):
        """Trim doesn't translate to batch mode - each source file has its
        own length, so a single in/out range picked against one preview
        wouldn't mean the same thing applied across the whole folder. Grey
        out the nav entry rather than leaving a page whose controls don't
        do anything useful."""
        batch = self._is_batch_mode()
        flags = self.trim_nav_item.flags()
        if batch:
            self.trim_nav_item.setFlags(flags & ~Qt.ItemIsEnabled)
            if self.section_list.currentItem() is self.trim_nav_item:
                self.section_list.setCurrentRow(0)
        else:
            self.trim_nav_item.setFlags(flags | Qt.ItemIsEnabled)
