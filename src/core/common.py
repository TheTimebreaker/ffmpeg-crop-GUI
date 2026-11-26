from typing import Any

from PySide6.QtWidgets import QWidget


class ToolTip:
    def __init__(self, widget: QWidget, text: str) -> None:
        widget.setToolTip(text)


def swap_list_indices(original_list: list[Any], index_a: int, index_b: int) -> list[Any]:
    original_list[index_a], original_list[index_b] = original_list[index_b], original_list[index_a]
    return original_list
