"""Source selection: the single-file and batch-folder tabs, the File Info
page (single-file details, or the batch summary/destination/queue table),
and the handlers behind them."""
from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import batch, probe

QUEUE_COLUMNS = [
    "File", "Container", "Video Codec", "Resolution", "Duration", "Size",
    "Alpha", "Status",
]


def _video_file_filter() -> str:
    patterns = " ".join(f"*{ext}" for ext in sorted(batch.VIDEO_EXTENSIONS))
    return f"Video files ({patterns});;All files (*)"


class SourceMixin:
    def _build_single_source_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(self._build_file_group())
        return tab

    def _build_file_group(self) -> QWidget:
        group = QWidget()
        outer = QVBoxLayout(group)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._section_heading("Input file"))
        row = QHBoxLayout()
        self.select_file_button = QPushButton("Select Video File…")
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setWordWrap(True)
        row.addWidget(self.select_file_button)
        row.addWidget(self.file_path_label, stretch=1)
        outer.addLayout(row)
        return group

    def _build_info_group(self) -> QWidget:
        group = QWidget()
        outer = QVBoxLayout(group)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._section_heading("Source file details"))
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(form_widget)
        self.info_labels = {}
        fields = [
            "container", "duration", "file_size", "overall_bitrate",
            "video_codec", "resolution", "frame_rate", "video_bitrate",
            "audio_codec", "audio_channels", "sample_rate", "audio_bitrate",
            "alpha",
        ]
        titles = {
            "container": "Container",
            "duration": "Duration",
            "file_size": "File size",
            "overall_bitrate": "Overall bitrate",
            "video_codec": "Video codec",
            "resolution": "Resolution",
            "frame_rate": "Frame rate",
            "video_bitrate": "Video bitrate",
            "audio_codec": "Audio codec",
            "audio_channels": "Audio channels",
            "sample_rate": "Sample rate",
            "audio_bitrate": "Audio bitrate",
            "alpha": "Alpha channel",
        }
        for key in fields:
            label = QLabel("—")
            # Deliberately not word-wrapped: QFormLayout doesn't reliably
            # grow a row's height to fit a wrapped label (its wrapped
            # second line ends up overlapping the row below instead) - a
            # long codec long-name just extends past the label's own
            # width unclipped instead, which reads fine against the page's
            # plain background. The actual long-single-line-inflates-the-
            # window bug this was guarding against is size_estimate_label
            # (see _build_command_preview_page), which is genuinely
            # wrapped since it isn't inside a QFormLayout.
            self.info_labels[key] = label
            form.addRow(titles[key] + ":", label)
        return group

    def _build_batch_source_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        layout.addWidget(self._section_heading("Source folder"))
        source_row = QHBoxLayout()
        self.select_folder_button = QPushButton("Select Source Folder…")
        self.source_folder_label = QLabel("No folder selected")
        self.source_folder_label.setWordWrap(True)
        self.recursive_check = QCheckBox("Include subfolders")
        source_row.addWidget(self.select_folder_button)
        source_row.addWidget(self.source_folder_label, stretch=1)
        source_row.addWidget(self.recursive_check)
        layout.addLayout(source_row)

        return tab

    def _build_file_info_page(self) -> QWidget:
        """Shows single-file source details, or (in batch mode) the folder
        summary, destination folder picker, and per-file queue - whichever
        is relevant is toggled visible by _update_file_info_page_visibility."""
        page = QWidget()
        layout = QVBoxLayout(page)

        self.info_group = self._build_info_group()
        layout.addWidget(self.info_group)

        self.batch_info_widget = QWidget()
        batch_layout = QVBoxLayout(self.batch_info_widget)
        batch_layout.setContentsMargins(0, 0, 0, 0)

        batch_layout.addWidget(self._section_heading("Folder summary"))
        self.batch_summary_label = QLabel("Select a source folder to scan for videos.")
        self.batch_summary_label.setWordWrap(True)
        batch_layout.addWidget(self.batch_summary_label)

        batch_layout.addWidget(self._section_heading("Destination folder"))
        dest_row = QHBoxLayout()
        self.select_dest_button = QPushButton("Select Destination Folder…")
        self.dest_folder_label = QLabel("No destination folder selected")
        self.dest_folder_label.setWordWrap(True)
        dest_row.addWidget(self.select_dest_button)
        dest_row.addWidget(self.dest_folder_label, stretch=1)
        batch_layout.addLayout(dest_row)

        batch_layout.addWidget(self._section_heading("Files"))
        self.queue_table = QTableWidget(0, len(QUEUE_COLUMNS))
        self.queue_table.setHorizontalHeaderLabels(QUEUE_COLUMNS)
        queue_header = self.queue_table.horizontalHeader()
        # "File" gets a generous fixed starting width (Interactive, not
        # Stretch - a Stretch column has no floor of its own and gets
        # crushed down to whatever's left once the other columns claim
        # their content-fit width, which was unreadable for anything but
        # short filenames). The rest are short, fixed-content columns
        # (codec names, "1920x1080", etc.) sized to their content; the
        # table scrolls horizontally rather than shrinking any of them
        # below that on a narrow window.
        queue_header.setSectionResizeMode(0, QHeaderView.Interactive)
        queue_header.resizeSection(0, 260)
        for col in range(1, len(QUEUE_COLUMNS)):
            queue_header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        # Container is the exception: ffprobe's format_name is often a
        # whole comma-separated alias list (e.g. "mov,mp4,m4a,3gp,3g2,mj2"
        # for an MP4) rather than a short label, which - sized to that
        # content like the rest - was consistently the widest column and
        # regularly pushed the table past the page's own width, forcing a
        # horizontal scrollbar on the whole content area rather than just
        # the table. Fixed and narrower instead; the full value is still on
        # its tooltip (see _queue_item).
        queue_header.setSectionResizeMode(1, QHeaderView.Interactive)
        queue_header.resizeSection(1, 90)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.queue_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.queue_table.setMinimumHeight(200)
        batch_layout.addWidget(self.queue_table, stretch=1)

        layout.addWidget(self.batch_info_widget)
        layout.addStretch(1)
        return page

    def _update_file_info_page_visibility(self):
        batch_mode = self._is_batch_mode()
        self.info_group.setVisible(not batch_mode)
        self.batch_info_widget.setVisible(batch_mode)

    def _on_mode_changed(self):
        self._update_alpha_group_state()
        self._update_output_controls_enabled()
        self._refresh_resolution_ui_state()
        self._update_crop_status()
        self._update_crop_controls_enabled()
        self._update_file_info_page_visibility()
        self._refresh_crop_preview()
        self._update_trim_nav_enabled()
        self._refresh_trim_source()
        self._rebuild_command_preview()

    # ------------------------------------------------------------------
    # Single file selection / probing
    # ------------------------------------------------------------------
    def _on_select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select video file", "", _video_file_filter(),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        try:
            info = probe.probe_file(path)
        except probe.ProbeError as exc:
            QMessageBox.critical(self, "Could not read file", str(exc))
            return

        self.media_info = info
        self.file_path_label.setText(path)
        self._populate_info_labels(info)
        self._crop_rect = None
        self._refresh_resolution_ui_state()
        self._update_crop_status()
        self._update_crop_controls_enabled()
        self._update_output_controls_enabled()
        self._update_alpha_group_state()
        self._update_computed_height()
        self._refresh_crop_preview()
        self._refresh_trim_source()
        self.status_label.setText("Ready.")
        self._rebuild_command_preview()

    def _populate_info_labels(self, info: probe.MediaInfo):
        self.info_labels["container"].setText(
            info.format_long_name or info.format_name or "unknown"
        )
        self.info_labels["duration"].setText(probe.human_duration(info.duration_s))
        self.info_labels["file_size"].setText(probe.human_size(info.size_bytes))
        self.info_labels["overall_bitrate"].setText(
            probe.human_bitrate(info.overall_bit_rate)
        )

        if info.video:
            v = info.video
            self.info_labels["video_codec"].setText(
                f"{v.codec_long_name or v.codec_name} ({v.codec_name})"
            )
            self.info_labels["resolution"].setText(f"{v.width} x {v.height}")
            self.info_labels["frame_rate"].setText(f"{v.fps:.2f} fps")
            self.info_labels["video_bitrate"].setText(probe.human_bitrate(v.bit_rate))
            self.info_labels["alpha"].setText(
                f"Yes ({v.pix_fmt})" if v.has_alpha else "No"
            )
        else:
            for k in ("video_codec", "resolution", "frame_rate", "video_bitrate", "alpha"):
                self.info_labels[k].setText("none")

        if info.audio:
            a = info.audio
            self.info_labels["audio_codec"].setText(
                f"{a.codec_long_name or a.codec_name} ({a.codec_name})"
            )
            self.info_labels["audio_channels"].setText(
                f"{a.channels} ({a.channel_layout})" if a.channel_layout else str(a.channels)
            )
            self.info_labels["sample_rate"].setText(f"{a.sample_rate} Hz")
            self.info_labels["audio_bitrate"].setText(probe.human_bitrate(a.bit_rate))
        else:
            for k in ("audio_codec", "audio_channels", "sample_rate", "audio_bitrate"):
                self.info_labels[k].setText("none")

    # ------------------------------------------------------------------
    # Batch folder selection / scanning
    # ------------------------------------------------------------------
    def _on_select_source_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select source folder", "",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not folder:
            return
        self.batch_source_folder = folder
        self.source_folder_label.setText(folder)
        self._scan_source_folder()

    def _on_recursive_toggled(self):
        if self.batch_source_folder:
            self._scan_source_folder()

    def _scan_source_folder(self):
        """Kicks off the scan on a background thread (see BatchScanner) and
        returns immediately - _on_batch_scan_item_probed/_finished pick up
        the results as they arrive, rather than blocking here until the
        whole folder (each file its own ffprobe subprocess call) is done."""
        folder = self.batch_source_folder
        if not folder:
            return
        self._crop_rect = None
        self._refresh_resolution_ui_state()
        self._update_crop_status()

        self.batch_items = []
        self.queue_table.setRowCount(0)
        self.batch_summary_label.setText("Scanning…")
        self.status_label.setText("Scanning…")
        self.select_folder_button.setEnabled(False)
        self.recursive_check.setEnabled(False)
        self._update_output_controls_enabled()

        self._batch_scanner.start(folder, self.recursive_check.isChecked())

    def _on_batch_scan_item_probed(self, item: batch.BatchItem, index: int, total: int):
        self.status_label.setText(f"Scanning {index}/{total}: {os.path.basename(item.input_path)}")

    def _on_batch_scan_finished(self, items: list[batch.BatchItem]):
        self.select_folder_button.setEnabled(True)
        self.recursive_check.setEnabled(True)

        self.batch_items = items
        if items:
            self.batch_summary_label.setText(batch.summarize(items))
            self._populate_queue_table(items)
        else:
            self.batch_summary_label.setText("No video files found in this folder.")
            self.queue_table.setRowCount(0)
        self.status_label.setText("Scan complete.")
        self._update_output_controls_enabled()
        self._update_alpha_group_state()
        self._update_crop_controls_enabled()
        self._update_computed_height()
        self._refresh_crop_preview()
        self._refresh_trim_source()
        self._rebuild_command_preview()

    @staticmethod
    def _queue_item(text: str, tooltip: str | None = None) -> QTableWidgetItem:
        """A cell whose tooltip shows its full content on hover - mainly
        for the File column (elidable even at its wider default width, and
        the file's full path besides), but applied uniformly so any column
        a user narrows by dragging stays readable on hover too."""
        item = QTableWidgetItem(text)
        item.setToolTip(tooltip if tooltip is not None else text)
        return item

    def _populate_queue_table(self, items: list[batch.BatchItem]):
        self.queue_table.setRowCount(len(items))
        self._item_row = {}
        for row, item in enumerate(items):
            self._item_row[item.input_path] = row
            self.queue_table.setItem(
                row, 0,
                self._queue_item(os.path.basename(item.input_path), tooltip=item.input_path),
            )
            if item.media_info:
                mi = item.media_info
                self.queue_table.setItem(row, 1, self._queue_item(mi.format_name or "—"))
                vcodec = mi.video.codec_name if mi.video else "—"
                self.queue_table.setItem(row, 2, self._queue_item(vcodec))
                res = f"{mi.video.width}x{mi.video.height}" if mi.video else "—"
                self.queue_table.setItem(row, 3, self._queue_item(res))
                self.queue_table.setItem(row, 4, self._queue_item(probe.human_duration(mi.duration_s)))
                self.queue_table.setItem(row, 5, self._queue_item(probe.human_size(mi.size_bytes)))
                self.queue_table.setItem(row, 6, self._queue_item("Yes" if mi.has_alpha else "No"))
            else:
                for col in range(1, 7):
                    self.queue_table.setItem(row, col, self._queue_item("—"))
            self.queue_table.setItem(row, 7, self._queue_item(item.status.value))

    def _refresh_queue_row(self, item: batch.BatchItem):
        row = self._item_row.get(item.input_path)
        if row is None:
            return
        self.queue_table.setItem(row, 7, self._queue_item(item.status.value))

    def _on_select_dest_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select destination folder", "",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not folder:
            return
        self.batch_dest_folder = folder
        self.dest_folder_label.setText(folder)
        self._update_output_controls_enabled()
