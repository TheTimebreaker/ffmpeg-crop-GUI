from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget


def select_font_path(parent: QWidget) -> Path | None:
    path, _ = QFileDialog.getOpenFileName(
        parent,
        "Select font file",
        "",
        "Font files (*.ttf *.otf *.ttc *.otc);;All files (*)",
    )
    return Path(path) if path else None
