"""Composition root: MainWindow itself (assembled from the mixins in this
package - see __init__.py for the map of what lives where), top-level UI
assembly, signal wiring, and window lifecycle. Anything that's really a
property of one specific page (File Info, Codec/Container, Size/Crop,
Trim, Audio, Alpha, Command Preview) lives in that page's own mixin
instead - this file is only what ties them together."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QRect, QSize, QTimer
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QProxyStyle, QPushButton, QScrollArea, QStackedWidget,
    QStyle, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget,
)

from .. import batch, icon_factory, probe
from ..about_dialog import AboutDialog
from ..batch_scan import BatchScanner
from ..converter import ConversionRunner
from ..ffmpeg_setup_dialog import FFmpegSetupDialog
from ..progress_dialog import ConversionProgressDialog
from ..theme import DIVIDER_COLOR
from ..trim_panel import TrimPanel
from .alpha_mixin import AlphaMixin
from .audio_mixin import AudioMixin
from .codec_container_mixin import CodecContainerMixin
from .conversion_mixin import ConversionMixin
from .crop_mixin import CropMixin, _CROP_SCRUB_DEBOUNCE_MS
from .output_preview_mixin import OutputPreviewMixin
from .profiles_mixin import ProfilesMixin
from .source_mixin import SourceMixin

# videoconverter/icons - resolved from this file's own location rather than
# a plain os.path.dirname(__file__), since this module lives one directory
# deeper (videoconverter/main_window/) than the package root the icons
# actually sit in.
PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS_DIR = os.path.join(PACKAGE_DIR, "icons")


class _AccentedTabStyle(QProxyStyle):
    """Recolors just the selected tab's thin accent line, without touching
    anything else about how the base style paints tabs.

    A QSS rule targeting QTabBar::tab:selected was tried first, but the
    moment any stylesheet rule touches that sub-control, Qt switches to its
    own CSS box-model painting for it wholesale - substituting its own
    default padding/sizing even for properties the rule never mentioned, so
    the selected tab ends up a visibly different size/shape from the
    (still natively-painted) unselected one. A QProxyStyle instead lets the
    real style (Breeze, whatever) paint the tab exactly as it always does,
    then draws one small rect on top - same geometry, same everything,
    just a different accent color where the base style would normally put
    its own."""

    ACCENT_HEIGHT = 3

    def __init__(self, accent: QColor):
        # No base style passed in: QProxyStyle takes ownership of (and will
        # delete) whatever style object it's given, so handing it the
        # live, shared application style here would be a double-free
        # waiting to happen. The no-argument form instead defers to
        # QApplication's current style dynamically, without owning it.
        super().__init__()
        self._accent = accent

    def drawControl(self, element, option, painter, widget=None):
        super().drawControl(element, option, painter, widget)
        if (
            element == QStyle.ControlElement.CE_TabBarTabShape
            and option.state & QStyle.StateFlag.State_Selected
        ):
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(self._accent)
            painter.drawRect(
                option.rect.x(), option.rect.y(), option.rect.width(), self.ACCENT_HEIGHT
            )
            painter.restore()


class MainWindow(
    QMainWindow,
    SourceMixin,
    ProfilesMixin,
    CodecContainerMixin,
    AudioMixin,
    CropMixin,
    AlphaMixin,
    OutputPreviewMixin,
    ConversionMixin,
):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VidKonverter")

        self.media_info: probe.MediaInfo | None = None
        self.runner: ConversionRunner | None = None

        self.batch_items: list[batch.BatchItem] = []
        self.batch_source_folder: str | None = None
        self.batch_dest_folder: str | None = None
        self._item_row: dict[str, int] = {}
        self._batch_scanner = BatchScanner(self)
        self._batch_scanner.item_probed.connect(self._on_batch_scan_item_probed)
        self._batch_scanner.finished.connect(self._on_batch_scan_finished)
        self._batch_queue: list[batch.BatchItem] = []
        self._batch_index: int = -1
        self._cancel_requested = False
        self._last_output_path: str | None = None
        self._progress_dialog: ConversionProgressDialog | None = None
        self._last_log_lines: list[str] = []
        self._profile_loaded = False

        self.source_has_alpha = False
        self._matte_color = QColor(0, 0, 0)
        self._crop_rect: QRect | None = None
        # Trim selection lives on trim_panel (TrimPanel) itself now - see
        # trim_panel.trim_range_seconds().

        # Coalesces rapid-fire value changes (slider drags, spin box
        # nudges) into a single command-preview/size-estimate rebuild ~150ms
        # after the last change, rather than recomputing - in batch mode,
        # over every queued item - on every intermediate value.
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._rebuild_command_preview)

        # The path _refresh_crop_preview last showed a frame from - lets it
        # tell "still the same source, just the crop/scrub position moved"
        # apart from "a genuinely different source," so only the latter
        # resets the scrubber back to a sensible starting position.
        self._crop_preview_path: str | None = None
        # Debounces the crop preview scrubber: extracting a frame is a
        # real (if quick) ffmpeg subprocess call, so re-running it on every
        # intermediate value while the user is actively dragging would
        # queue those up and make the drag itself feel laggy - wait for a
        # short pause instead.
        self._crop_scrub_timer = QTimer(self)
        self._crop_scrub_timer.setSingleShot(True)
        self._crop_scrub_timer.setInterval(_CROP_SCRUB_DEBOUNCE_MS)
        self._crop_scrub_timer.timeout.connect(self._refresh_crop_preview)

        self._build_ui()
        self._build_tray_icon()
        self._connect_signals()
        self._check_ffmpeg()
        self._refresh_profile_combo()
        self._update_output_controls_enabled()
        self._update_alpha_group_state()
        self._refresh_resolution_ui_state()
        self._update_crop_status()
        self._update_crop_controls_enabled()
        self._update_file_info_page_visibility()
        self._update_trim_nav_enabled()
        self._refresh_trim_source()
        self._rebuild_command_preview()

        # Start compact-but-comfortable: tall enough that the detail pages
        # render without a scrollbar, but not the old fixed 900x900 that
        # left empty space below the progress bar/log (hidden until a
        # conversion starts). This is Qt's logical content height, which
        # excludes the window manager's title bar and drop shadow - on this
        # KDE/Wayland session that chrome adds ~158px on top of whatever is
        # set here, so a target of an ~800px *on-screen* window works out to
        # roughly 640 of actual content height.
        self.resize(910, 670)
        self.setMinimumSize(910, 670)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        help_menu = self.menuBar().addMenu("&Help")
        ffmpeg_setup_action = help_menu.addAction("FFmpeg Setup…")
        ffmpeg_setup_action.triggered.connect(self._show_ffmpeg_setup_dialog)
        help_menu.addSeparator()
        about_action = help_menu.addAction("About VidKonverter")
        about_action.triggered.connect(self._show_about_dialog)

        central = QWidget()
        # QScrollArea defaults to a sunken/rounded panel frame around
        # itself, and its viewport paints the Base palette role - which,
        # without this, reads as a light grey rounded box floating inside
        # the plain-background window, distinct from the export button and
        # status label below it. Dropping the frame and giving the whole
        # central widget that same Base background makes everything below
        # the menu bar read as one flat surface instead.
        #
        # Set via QPalette, not a stylesheet: a QSS rule on an ancestor
        # widget makes Qt fall back to its own generic (non-native) CSS
        # painting for every descendant that has any styleable chrome of
        # its own - scrollbars included, which is why they'd previously
        # come out as plain flat-square Qt/Fusion-ish bars instead of the
        # native, subtle, rounded Breeze ones (the same class of issue
        # _AccentedTabStyle works around for the tab bar's accent line).
        # A palette role carries no such cost - native painting is
        # unaffected.
        central_palette = central.palette()
        central_palette.setColor(QPalette.Window, central_palette.color(QPalette.Base))
        central.setPalette(central_palette)
        central.setAutoFillBackground(True)
        outer_layout = QVBoxLayout(central)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer_layout.addWidget(scroll, stretch=1)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)

        # Row 1: source selection (single file, or batch source folder).
        self.mode_tabs = QTabWidget()
        self.single_tab = self._build_single_source_tab()
        self.batch_tab = self._build_batch_source_tab()
        self.mode_tabs.addTab(self.single_tab, "Single File")
        self.mode_tabs.addTab(self.batch_tab, "Batch Folder")
        # See _AccentedTabStyle - recolors just the active-tab accent line
        # via a QProxyStyle rather than a stylesheet, so tab padding/shape
        # stays whatever the real (Breeze) style already draws.
        self._tab_accent_style = _AccentedTabStyle(QColor("#51A2DA"))
        self.mode_tabs.tabBar().setStyle(self._tab_accent_style)
        layout.addWidget(self.mode_tabs)

        # Row 1.5: profile shortcuts, kept separate from source selection.
        layout.addWidget(self._build_profile_row())

        # Row 2: section nav (left) + the matching detail page (right).
        layout.addLayout(self._build_detail_row())

        layout.addStretch(1)

        action_row = QHBoxLayout()
        self.convert_button = QPushButton("Start Export")
        self.convert_button.setIcon(icon_factory.export_icon(QColor("#333333")))
        self.convert_button.setMinimumHeight(36)
        self.convert_button.setStyleSheet(
            "QPushButton { background-color: #51A2DA; color: #333333; }"
            "QPushButton:hover { background-color: #6BB0E0; }"
            "QPushButton:pressed { background-color: #3E86BD; }"
        )
        action_row.addWidget(self.convert_button)
        outer_layout.addLayout(action_row)

        # Progress and the ffmpeg log live in a modal ConversionProgressDialog
        # (see progress_dialog.py) shown for the duration of a conversion,
        # rather than inline here.
        self.status_label = QLabel("Select a file to begin.")
        # Outside the scroll area, so this one won't force the page-level
        # horizontal scrollbar size_estimate_label did - but a long scan
        # status (a long filename, "Scanning 5/11: ...") could still push
        # the window's own effective minimum width wider than it should be.
        self.status_label.setWordWrap(True)
        outer_layout.addWidget(self.status_label)

        self.setCentralWidget(central)

    def _build_tray_icon(self):
        icon = QIcon(os.path.join(ICONS_DIR, "vidkonverter-app-icon.png"))
        self.setWindowIcon(icon)
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("VidKonverter")

    def _notify(self, title: str, message: str, warning: bool = False):
        """Show a native desktop notification, if the platform supports one."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if not self.tray_icon.isVisible():
            self.tray_icon.show()
        icon = QSystemTrayIcon.Warning if warning else QSystemTrayIcon.Information
        self.tray_icon.showMessage(title, message, icon, 8000)

    @staticmethod
    def _section_heading(text: str) -> QLabel:
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    def _build_detail_row(self) -> QHBoxLayout:
        row = QHBoxLayout()

        self.section_list = QListWidget()
        # Fixed, not just capped - a wide detail page (e.g. the batch queue
        # table's own minimum width, once it's not just an infinitely
        # squeezable Stretch column) can otherwise pressure this narrower
        # rather than scroll/grow the page instead.
        self.section_list.setFixedWidth(190)
        self.section_list.setIconSize(QSize(22, 22))
        self.section_list.setFrameShape(QFrame.NoFrame)
        # Everything in row 2 sits inside the outer QScrollArea, whose
        # viewport Qt auto-fills with the Base palette role - so that's what
        # the detail pages actually render as, not Window. QListWidget
        # already defaults to Base too; pin it explicitly (it's also a
        # scroll area, with its own viewport) and drop its frame so it reads
        # as one flat surface with the detail pages, divided only by the
        # line added below.
        self.section_list.setStyleSheet(
            "QListWidget { background: palette(base); border: none; }"
            "QListWidget::item { padding: 4px 2px; }"
        )

        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Plain)
        divider.setStyleSheet(f"color: {DIVIDER_COLOR};")

        sections = [
            ("File Info", "fileinfo.png"),
            ("Codec / Container", "codec.png"),
            ("Size / Crop", "crop.png"),
            ("Trim", "trim.png"),
            ("Audio", "audio.png"),
            ("Command Preview", "command.png"),
        ]
        for label, icon_file in sections:
            icon = QIcon(os.path.join(ICONS_DIR, icon_file))
            item = QListWidgetItem(icon, label, self.section_list)
            if label == "Trim":
                self.trim_nav_item = item

        self.detail_stack = QStackedWidget()
        self.detail_stack.addWidget(self._build_file_info_page())
        self.detail_stack.addWidget(self._build_codec_container_page())
        self.detail_stack.addWidget(self._build_size_crop_page())
        self.trim_panel = TrimPanel(self)
        self.detail_stack.addWidget(self.trim_panel)
        self.detail_stack.addWidget(self._build_audio_page())
        self.detail_stack.addWidget(self._build_command_preview_page())

        # All widgets referenced by alpha/container restriction now exist.
        self._apply_alpha_container_restriction()

        self.section_list.currentRowChanged.connect(self.detail_stack.setCurrentIndex)
        self.section_list.setCurrentRow(0)

        row.addWidget(self.section_list)
        row.addWidget(divider)
        row.addWidget(self.detail_stack, stretch=1)
        return row

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_signals(self):
        self.select_file_button.clicked.connect(self._on_select_file)
        self.convert_button.clicked.connect(self._on_convert_clicked)

        self.select_folder_button.clicked.connect(self._on_select_source_folder)
        self.recursive_check.toggled.connect(self._on_recursive_toggled)
        self.select_dest_button.clicked.connect(self._on_select_dest_folder)
        self.mode_tabs.currentChanged.connect(self._on_mode_changed)

        self.load_profile_button.clicked.connect(self._on_load_profile_clicked)
        self.update_profile_button.clicked.connect(self._on_update_profile_clicked)
        self.save_profile_button.clicked.connect(self._on_save_profile_clicked)
        self.delete_profile_button.clicked.connect(self._on_delete_profile_clicked)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selection_changed)

        self.container_combo.currentTextChanged.connect(self._on_container_changed)
        self.video_codec_combo.currentTextChanged.connect(self._on_video_codec_changed)
        self.crf_radio.toggled.connect(self._on_quality_mode_changed)
        self.resolution_combo.currentTextChanged.connect(self._on_resolution_changed)
        self.keep_aspect_check.toggled.connect(self._on_resolution_changed)
        self.audio_copy_radio.toggled.connect(self._on_audio_mode_changed)
        self.audio_encode_radio.toggled.connect(self._on_audio_mode_changed)
        self.audio_remove_radio.toggled.connect(self._on_audio_mode_changed)
        self.fps_combo.currentTextChanged.connect(self._on_fps_mode_changed)

        self.custom_width_spin.valueChanged.connect(self._update_computed_height)
        self.keep_aspect_check.toggled.connect(self._update_computed_height)
        self.custom_height_spin.valueChanged.connect(self._update_crop_status)

        self.crf_slider.valueChanged.connect(self._on_crf_slider_changed)
        self.crf_spin.valueChanged.connect(self._on_crf_spin_changed)

        self.preserve_alpha_radio.toggled.connect(self._on_alpha_mode_changed)
        self.flatten_alpha_radio.toggled.connect(self._on_alpha_mode_changed)
        self.matte_color_button.clicked.connect(self._on_choose_matte_color)

        self.set_crop_button.clicked.connect(self._on_set_crop_clicked)
        self.reset_crop_button.clicked.connect(self._on_reset_crop_clicked)
        self.crop_scrub_slider.sliderMoved.connect(self._on_crop_scrub_moved)

        # All of the Trim page's own controls (Set/Go-to, typed fields,
        # Reset, transport) are wired up internally by TrimPanel already -
        # this is just its one external signal.
        self.trim_panel.settingsChanged.connect(self._rebuild_command_preview)

        for w in (
            self.container_combo, self.video_codec_combo, self.preset_combo,
            self.resolution_combo, self.audio_codec_combo, self.fps_combo,
        ):
            w.currentTextChanged.connect(self._rebuild_command_preview)
        # These fire many times in quick succession while being dragged -
        # route them through the debounced scheduler (see _preview_timer)
        # rather than triggering a full rebuild (and, in batch mode, a
        # per-item size re-estimate) on every intermediate value.
        for w in (
            self.crf_slider, self.crf_spin, self.bitrate_spin,
            self.custom_width_spin, self.custom_height_spin, self.audio_bitrate_spin,
        ):
            w.valueChanged.connect(self._schedule_command_preview_rebuild)
        self.custom_fps_spin.valueChanged.connect(self._schedule_command_preview_rebuild)
        self.keep_aspect_check.toggled.connect(self._rebuild_command_preview)
        self.faststart_check.toggled.connect(self._rebuild_command_preview)
        self.crf_radio.toggled.connect(self._rebuild_command_preview)
        self.audio_copy_radio.toggled.connect(self._rebuild_command_preview)
        self.audio_encode_radio.toggled.connect(self._rebuild_command_preview)
        self.audio_remove_radio.toggled.connect(self._rebuild_command_preview)
        self.preserve_alpha_radio.toggled.connect(self._rebuild_command_preview)
        self.flatten_alpha_radio.toggled.connect(self._rebuild_command_preview)

    def _check_ffmpeg(self):
        if probe.ffmpeg_available() and probe.ffprobe_available():
            return
        self.select_file_button.setEnabled(False)
        self.select_folder_button.setEnabled(False)
        self._show_ffmpeg_setup_dialog()

    def _show_ffmpeg_setup_dialog(self):
        dialog = FFmpegSetupDialog(self)
        dialog.exec()
        if probe.ffmpeg_available() and probe.ffprobe_available():
            self.select_file_button.setEnabled(True)
            self.select_folder_button.setEnabled(True)
            self.status_label.setText("ffmpeg detected. Ready.")
        else:
            self.status_label.setText(
                "ffmpeg is still not available. Use File → FFmpeg Setup… to try again."
            )

    def _show_about_dialog(self):
        AboutDialog(self).exec()

    # ------------------------------------------------------------------
    # Dynamic UI behaviour
    # ------------------------------------------------------------------
    def _is_batch_mode(self) -> bool:
        return self.mode_tabs.currentWidget() is self.batch_tab

    def _current_media_info(self) -> probe.MediaInfo | None:
        """The MediaInfo that source-dependent UI (dimensions, duration,
        crop/trim previews, etc) should read from: the first video-bearing
        item in the batch queue in batch mode, or the single selected file
        otherwise. This is the one place that branches on batch-vs-single -
        _current_source_dims/_current_crop_reference/_current_crop_media_info
        are all just narrower views onto it."""
        if self._is_batch_mode():
            sample = next(
                (i for i in self.batch_items if i.media_info and i.media_info.video), None
            )
            return sample.media_info if sample else None
        if self.media_info and self.media_info.video:
            return self.media_info
        return None

    def _current_source_dims(self):
        info = self._current_media_info()
        return (info.video.width, info.video.height) if info else None

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        if self.runner:
            reply = QMessageBox.question(
                self, "Conversion in progress",
                "A conversion is still running. Cancel it and quit?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._cancel_requested = True
                self.runner.cancel()
                self._close_progress_dialog()
            else:
                event.ignore()
                return
        self.trim_panel.stop_playback()
        self._batch_scanner.shutdown()
        self.tray_icon.hide()
        event.accept()
