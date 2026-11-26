from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core import common, filters, gui_vars
from core.fontselector import select_font_path

if TYPE_CHECKING:
    from main import GUI


class VideofilterArgsDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        required_args: list[str] | None = None,
        optional_args: list[str] | None = None,
        prefilled_args: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add FFmpeg Filter Arguments")
        self.setMinimumWidth(560)
        self.required_args = required_args or []
        self.optional_args = optional_args or []
        self.values = list((prefilled_args or {}).items()) or [("", "")]
        self.args: list[tuple[str, str]] = []

        layout = QVBoxLayout(self)
        self.rows_layout = QGridLayout()
        self.rows_layout.addWidget(QLabel("Argument"), 0, 0)
        self.rows_layout.addWidget(QLabel("Value"), 0, 1)
        self.rows_layout.addWidget(QLabel(""), 0, 2)
        layout.addLayout(self.rows_layout)

        add_button = QPushButton("Add row")
        add_button.clicked.connect(self.add_row)
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignLeft)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh_table()

    def add_row(self) -> None:
        self.values.append(("", ""))
        self.refresh_table()

    def remove_row(self, index: int) -> None:
        self.values.pop(index)
        if not self.values:
            self.values.append(("", ""))
        self.refresh_table()

    def refresh_table(self) -> None:
        while self.rows_layout.count() > 3:
            item = self.rows_layout.takeAt(3)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

        options = self.required_args + self.optional_args
        for index, (arg, value) in enumerate(self.values, start=1):
            arg_box = QComboBox()
            arg_box.setEditable(True)
            arg_box.addItems(options)
            arg_box.setCurrentText(arg)
            arg_box.currentTextChanged.connect(lambda text, row=index - 1: self._argument_changed(row, text))
            self.rows_layout.addWidget(arg_box, index, 0)

            value_row = QWidget()
            value_layout = QHBoxLayout(value_row)
            value_layout.setContentsMargins(0, 0, 0, 0)
            value_edit = QLineEdit(value)
            value_layout.addWidget(value_edit, 1)
            self.values[index - 1] = (arg, value)
            value_edit.textChanged.connect(lambda text, row=index - 1: self._value_changed(row, text))
            if arg == "fontfile":
                browse = QPushButton("Browse…")
                browse.clicked.connect(lambda _checked=False, edit=value_edit: self._browse_font(edit))
                value_layout.addWidget(browse)
            self.rows_layout.addWidget(value_row, index, 1)
            remove = QPushButton("Remove")
            remove.clicked.connect(lambda _checked=False, row=index - 1: self.remove_row(row))
            self.rows_layout.addWidget(remove, index, 2)

    def _argument_changed(self, row: int, text: str) -> None:
        _, value = self.values[row]
        self.values[row] = (text, value)
        if text == "fontfile":
            item = self.rows_layout.itemAtPosition(row + 1, 1)
            edit = item.widget() if item is not None else None
            if edit is not None:
                line_edit = edit.findChild(QLineEdit)
                if line_edit is not None:
                    self._browse_font(line_edit)

    def _value_changed(self, row: int, text: str) -> None:
        arg, _ = self.values[row]
        self.values[row] = (arg, text)

    @staticmethod
    def _browse_font(edit: QLineEdit) -> None:
        path = select_font_path(edit)
        if path:
            edit.setText(str(path))

    def on_ok(self) -> None:
        args = [(arg.strip(), value) for arg, value in self.values if arg.strip()]
        present = {arg for arg, _ in args}
        missing = [arg for arg in self.required_args if arg not in present]
        if missing:
            QMessageBox.critical(self, "Missing Required Arguments", f"Missing required arguments:\n\n{', '.join(missing)}")
            return
        self.args = args
        self.accept()


class Videofilter(QWidget):
    def __init__(self, parent: GUI, state: gui_vars.GuiVars) -> None:
        super().__init__()
        self.gui_vars = state
        self.controller = parent
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Video filter"))
        self.filter_box = QComboBox()
        self.filter_box.setEditable(True)
        self.filter_box.addItems(filters.SUPPORTED_FILTERS)
        self.filter_box.setCurrentText("")
        controls.addWidget(self.filter_box, 1)
        self.add_button = QPushButton("Add selected filter")
        self.add_button.clicked.connect(self.addvideofilter_dialog)
        controls.addWidget(self.add_button)
        layout.addLayout(controls)

        help_label = QLabel("FFmpeg video filters are powerful; check the official documentation before use.")
        help_label.setWordWrap(True)
        common.ToolTip(
            help_label,
            "This section performs limited validation. Incorrect filter arguments can cause FFmpeg to fail.",
        )
        layout.addWidget(help_label)

        self.filter_scroll = QScrollArea()
        self.filter_scroll.setWidgetResizable(True)
        self.filter_content = QWidget()
        self.filter_layout = QVBoxLayout(self.filter_content)
        self.filter_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.filter_scroll.setWidget(self.filter_content)
        layout.addWidget(self.filter_scroll, 1)
        self.update_videofilter_preview()

    def swap_videofilter_args(self, index_a: int, index_b: int) -> None:
        common.swap_list_indices(self.gui_vars.video_filter_args, index_a, index_b)
        self.update_videofilter_preview()

    def update_videofilter_preview(self) -> None:
        while self.filter_layout.count():
            item = self.filter_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

        for index, (filter_name, entry) in enumerate(self.gui_vars.video_filter_args):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 2, 0, 2)
            up = QPushButton("↑")
            up.setEnabled(index > 0)
            up.clicked.connect(lambda _checked=False, i=index: self.swap_videofilter_args(i, i - 1))
            down = QPushButton("↓")
            down.setEnabled(index < len(self.gui_vars.video_filter_args) - 1)
            down.clicked.connect(lambda _checked=False, i=index: self.swap_videofilter_args(i, i + 1))
            row_layout.addWidget(up)
            row_layout.addWidget(down)
            row_layout.addWidget(QLabel(filter_name))
            args_label = QLabel(str(entry))
            args_label.setWordWrap(True)
            row_layout.addWidget(args_label, 1)
            edit = QPushButton("Edit")
            edit.clicked.connect(lambda _checked=False, f=filter_name, e=entry: self.editvideofilter_dialog(f, e))
            remove = QPushButton("Remove")
            remove.clicked.connect(lambda _checked=False, f=filter_name, e=entry: self.removevideofilter(f, e))
            row_layout.addWidget(edit)
            row_layout.addWidget(remove)
            self.filter_layout.addWidget(row)

    def addvideofilter_dialog(
        self,
        prefilled_args: dict[str, str] | None = None,
        replace_index: int | None = None,
        filter: filters.FiltersLiteral | None = None,
    ) -> None:
        selected = filter or self.filter_box.currentText()
        if selected not in filters.SUPPORTED_FILTERS:
            QMessageBox.critical(self, "Unknown filter", "Select one of the supported filters first.")
            return
        selected_filter = cast(filters.FiltersLiteral, selected)
        required, optional = filters.filter_arguments(selected_filter)
        dialog = VideofilterArgsDialog(self, required, optional, prefilled_args)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        args = dict(dialog.args)
        if replace_index is None:
            self.gui_vars.video_filter_args.append((selected_filter, args))
        else:
            self.gui_vars.video_filter_args[replace_index] = (selected_filter, args)
        self.update_videofilter_preview()

    def removevideofilter(self, filter_to_remove: filters.FiltersLiteral, args_to_remove: dict[str, str]) -> None:
        try:
            self.gui_vars.video_filter_args.remove((filter_to_remove, args_to_remove))
        except ValueError:
            return
        self.update_videofilter_preview()

    def editvideofilter_dialog(self, filter_to_edit: filters.FiltersLiteral, args_to_edit: dict[str, str]) -> None:
        for index, (filter_name, args) in enumerate(self.gui_vars.video_filter_args):
            if filter_name == filter_to_edit and args == args_to_edit:
                self.addvideofilter_dialog(args_to_edit, replace_index=index, filter=filter_to_edit)
                return
