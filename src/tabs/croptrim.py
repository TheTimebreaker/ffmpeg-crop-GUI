from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QSpinBox, QVBoxLayout, QWidget

from core import common, gui_vars

if TYPE_CHECKING:
    from main import GUI


class CropTrim(QWidget):
    def __init__(self, parent: GUI, state: gui_vars.GuiVars) -> None:
        super().__init__()
        self.gui_vars = state
        self.controller = parent
        self._spinboxes: dict[tuple[str, str], QSpinBox] = {}
        self._build_ui()

    def _value(self, section: str, key: str) -> gui_vars.Value:
        return self.gui_vars.settings[section][key]["var"]

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)

        crop_group = QGroupBox("Crop")
        crop_layout = QFormLayout(crop_group)
        self.crop_enabled = QCheckBox("Enable crop")
        self.crop_enabled.toggled.connect(self._value("crop", "crop_enabled").set)
        crop_layout.addRow("", self.crop_enabled)
        crop_layout.addRow("Top-left corner (X / Y)", self._spin_pair("crop", "left_top_x", "left_top_y"))
        crop_layout.addRow("Box dimensions (width / height)", self._spin_pair("crop", "width", "height"))
        common.ToolTip(
            self.crop_enabled,
            "Crop the video using the values below. The crop is only applied if the values differ from the original video.",
        )
        layout.addWidget(crop_group)

        trim_group = QGroupBox("Trim")
        trim_layout = QFormLayout(trim_group)
        self.trim_enabled = QCheckBox("Enable trim")
        self.trim_enabled.toggled.connect(self._value("trim", "trim_enabled").set)
        trim_layout.addRow("", self.trim_enabled)
        trim_layout.addRow("Start (HH : MM : SS . MS)", self._time_fields("start"))
        trim_layout.addRow("End (HH : MM : SS . MS)", self._time_fields("end"))
        common.ToolTip(
            self.trim_enabled,
            "Trim the video using the timestamps below. Trimming is only applied if the timestamps differ from the original.",
        )
        layout.addWidget(trim_group)
        layout.addStretch(1)
        self.sync_controls()

    def _spin_pair(self, section: str, first: str, second: str) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self._spinbox(section, first, 0, 50000))
        row_layout.addWidget(self._spinbox(section, second, 0, 50000))
        return row

    def _time_fields(self, which: str) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        for index, (suffix, maximum) in enumerate((("hh", 99), ("mm", 59), ("ss", 59), ("ms", 999))):
            if index:
                row_layout.addWidget(self._separator("." if index == 3 else ":"))
            key = f"{suffix}_{which}"
            row_layout.addWidget(self._spinbox("trim", key, 0, maximum))
        row_layout.addStretch(1)
        return row

    @staticmethod
    def _separator(text: str) -> QWidget:
        from PySide6.QtWidgets import QLabel

        return QLabel(text)

    def _spinbox(self, section: str, key: str, minimum: int, maximum: int) -> QSpinBox:
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setKeyboardTracking(False)
        box.valueChanged.connect(self._value(section, key).set)
        self._spinboxes[(section, key)] = box
        return box

    def sync_controls(self) -> None:
        self.crop_enabled.setChecked(self.gui_vars.settings["crop"]["crop_enabled"]["var"].get())
        self.trim_enabled.setChecked(self.gui_vars.settings["trim"]["trim_enabled"]["var"].get())
        for (section, key), box in self._spinboxes.items():
            box.setValue(self.gui_vars.settings[section][key]["var"].get())
