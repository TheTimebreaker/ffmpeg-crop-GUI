import tkinter as tk
from typing import Any


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None

        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, _event: Any = None) -> None:
        if self.tip_window:
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)  # removes window decorations
        self.tip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tip_window, text=self.text, background="#ffffe0", relief="solid", borderwidth=1, padx=5, pady=3, justify="left", anchor="w"
        )
        label.pack()

    def hide_tooltip(self, _event: Any = None) -> None:
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None
