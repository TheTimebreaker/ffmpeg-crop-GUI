from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import TYPE_CHECKING, Final, override

from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core import common, gui_vars, media_info

if TYPE_CHECKING:
    from main import GUI


class DoubleClickLabel(QLabel):
    def __init__(self, callback: Callable[[], None]) -> None:
        super().__init__()
        self._callback = callback

    @override
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self._callback()
        super().mouseDoubleClickEvent(event)


class InOut(QWidget):
    CODECS_VIDEO: Final = ("libx264", "libx265")
    PRESETS: Final = ("ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo")
    TUNES: Final = {
        "libx264": ("DEFAULT", "film", "animation", "grain", "stillimage", "fastdecode", "zerolatency"),
        "libx265": ("DEFAULT", "grain", "fastdecode", "zerolatency"),
    }

    def __init__(self, parent: GUI, state: gui_vars.GuiVars) -> None:
        super().__init__()
        self.controller = parent
        self.gui_vars = state
        self._build_ui()

    def _value(self, section: str, key: str) -> gui_vars.Value:
        return self.gui_vars.settings[section][key]["var"]

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)

        source_group = QGroupBox("Source file")
        source_layout = QHBoxLayout(source_group)
        self.file_label = DoubleClickLabel(self.set_file_dialogue)
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.file_label.setWordWrap(True)
        self.file_label.setMinimumHeight(44)
        self.file_label.setStyleSheet("QLabel { padding: 8px; border: 1px solid palette(mid); border-radius: 4px; }")
        self.browse_button = self._button("Browse…", self.set_file_dialogue)
        source_layout.addWidget(self.file_label, 1)
        source_layout.addWidget(self.browse_button)
        layout.addWidget(source_group)

        source_separator = QFrame()
        source_separator.setFrameShape(QFrame.Shape.HLine)
        source_separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(source_separator)

        audio_encoder_group = QGroupBox("Audio encoder")
        audio_encoder_layout = QFormLayout(audio_encoder_group)
        self.normalize_audio = QCheckBox("Automatically normalize audio to -1.0 dB")
        self.normalize_audio.toggled.connect(self._value("general", "normalize_audio").set)
        audio_encoder_layout.addRow("", self.normalize_audio)
        layout.addWidget(audio_encoder_group)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        self.video_encoder_group = QGroupBox("Video encoder")
        video_encoder_layout = QVBoxLayout(self.video_encoder_group)
        video_encoder_settings = QWidget()
        video_encoder_form = QFormLayout(video_encoder_settings)
        self.force_reencoding = QCheckBox("Force reencoding")
        self.force_reencoding.toggled.connect(self._value("general", "force_reencoding_video").set)
        video_encoder_form.addRow("Re-encode", self.force_reencoding)
        common.ToolTip(
            self.force_reencoding,
            "Video is copied when possible and only re-encoded when required. Cropping and trimming require re-encoding.",
        )

        self.encoder = QComboBox()
        self.encoder.addItems(self.CODECS_VIDEO)
        self.encoder.currentTextChanged.connect(self._select_encoder)
        video_encoder_form.addRow("Codec", self.encoder)
        video_encoder_layout.addWidget(video_encoder_settings)
        layout.addWidget(self.video_encoder_group)

        self.codec_options: dict[str, QGroupBox] = {}
        self.crf_sliders: dict[str, QSlider] = {}
        self.preset_boxes: dict[str, QComboBox] = {}
        self.tune_boxes: dict[str, QComboBox] = {}
        for codec in self.CODECS_VIDEO:
            group = QGroupBox(f"{codec} options")
            form = QFormLayout(group)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 51)
            slider.valueChanged.connect(self._value(codec, "crf").set)
            slider_value = QLabel()
            slider.valueChanged.connect(lambda value, label=slider_value: label.setText(str(value)))
            slider_row = QWidget()
            slider_layout = QHBoxLayout(slider_row)
            slider_layout.setContentsMargins(0, 0, 0, 0)
            slider_layout.addWidget(slider, 1)
            slider_layout.addWidget(slider_value)
            form.addRow("CRF", slider_row)
            common.ToolTip(
                slider,
                "Constant Rate Factor: lower values mean higher quality and larger files. 0 is lossless; 51 is the lowest quality.",
            )

            preset = QComboBox()
            preset.addItems(self.PRESETS)
            preset.currentTextChanged.connect(self._value(codec, "preset").set)
            form.addRow("Preset", preset)
            common.ToolTip(preset, "Slower presets trade encoding time for better compression. The default is medium.")

            tune = QComboBox()
            tune.addItems(self.TUNES[codec])
            tune.currentTextChanged.connect(self._value(codec, "tune").set)
            form.addRow("Tune", tune)

            self.codec_options[codec] = group
            self.crf_sliders[codec] = slider
            self.preset_boxes[codec] = preset
            self.tune_boxes[codec] = tune
            video_encoder_layout.addWidget(group)

        layout.addStretch(1)
        self.sync_controls()

    @staticmethod
    def _button(text: str, callback: Callable[..., None]) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(callback)
        return button

    def _select_encoder(self, encoder: str) -> None:
        self._value("general", "selected_encoder_video").set(encoder)
        self.update_codec_frames()

    def update_codec_frames(self) -> None:
        selected = self.gui_vars.settings["general"]["selected_encoder_video"]["var"].get()
        for codec, group in self.codec_options.items():
            group.setVisible(codec == selected)

    def sync_controls(self) -> None:
        path = self.gui_vars.settings["general"]["file"]["var"].get()
        self.file_label.setText(str(path) if path else "Double-click or drop a video file here")
        self.normalize_audio.setChecked(self.gui_vars.settings["general"]["normalize_audio"]["var"].get())
        self.force_reencoding.setChecked(self.gui_vars.settings["general"]["force_reencoding_video"]["var"].get())
        encoder = self.gui_vars.settings["general"]["selected_encoder_video"]["var"].get()
        self.encoder.setCurrentText(encoder)
        for codec in self.CODECS_VIDEO:
            self.crf_sliders[codec].setValue(self.gui_vars.settings[codec]["crf"]["var"].get())
            self.preset_boxes[codec].setCurrentText(self.gui_vars.settings[codec]["preset"]["var"].get())
            self.tune_boxes[codec].setCurrentText(self.gui_vars.settings[codec]["tune"]["var"].get())
        self.update_codec_frames()

    def set_file_dialogue(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select video file", "", "Video files (*)")
        if path:
            self.set_file(path)

    def set_file(self, path: str) -> None:
        try:
            video = media_info.get_video_info(path)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError) as error:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "Unable to read video", str(error))
            return

        self.controller._reset_to_defaults()
        self.controller.max_volume = video.max_volume
        self.gui_vars.settings["general"]["file"]["var"].set(path)
        duration = video.duration
        if duration.hh is None or duration.mm is None or duration.ss is None or duration.ms is None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "Unable to read video", "The video duration could not be determined.")
            return
        for key, value in (
            ("width", video.width),
            ("height", video.height),
            ("original_width", video.width),
            ("original_height", video.height),
            ("left_top_x", 0),
            ("left_top_y", 0),
            ("original_left_top_x", 0),
            ("original_left_top_y", 0),
        ):
            self.gui_vars.settings["crop"][key]["var"].set(value)

        for key, value in (
            ("hh_start", 0),
            ("mm_start", 0),
            ("ss_start", 0),
            ("ms_start", 0),
            ("hh_end", duration.hh),
            ("mm_end", duration.mm),
            ("ss_end", duration.ss),
            ("ms_end", duration.ms),
            ("original_hh_end", duration.hh),
            ("original_mm_end", duration.mm),
            ("original_ss_end", duration.ss),
            ("original_ms_end", duration.ms),
        ):
            self.gui_vars.settings["trim"][key]["var"].set(value)
        self.controller.sync_controls()
