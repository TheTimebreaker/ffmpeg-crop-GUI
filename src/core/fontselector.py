from __future__ import annotations

import os
import random
import string
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Any, Literal

from fontTools.ttLib import TTFont  # type:ignore


def select_font_path(parent: tk.Tk | tk.Toplevel) -> Path | Literal[False]:
    dialog = SearchableFont(parent)
    if dialog.selection:
        return Path(dialog.fonts_dir).joinpath(dialog.selection)
    return False


def get_font_family(font_path: str) -> str:
    font_obj = TTFont(font_path)
    for record in font_obj["name"].names:
        if record.nameID == 1:
            try:
                if b"\x00" in record.string:
                    return str(record.string.decode("utf-16-be"))
                else:
                    return str(record.string.decode("utf-8"))
            except UnicodeDecodeError:
                return str(record.string.decode("latin-1"))
    return "UnknownFamily"


def create_fake_font(root: tk.Tk | tk.Toplevel, font_path: str, font_size: int = 12) -> str:
    family = get_font_family(font_path)
    fake_identity = "".join(random.choice(string.ascii_letters) for _ in range(8))
    root.tk.call("font", "create", fake_identity, "-family", family, "-size", font_size)

    return fake_identity


class SearchableFont:
    def __init__(self, parent: tk.Tk | tk.Toplevel, fonts_dir: str | None = None) -> None:
        self.top = tk.Toplevel(parent)
        self.top.transient(parent)
        self.top.title("Select your option")
        self.top.grab_set()
        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)

        if fonts_dir is None:
            if sys.platform == "win32":
                fonts_dir = r"C:\Windows\Fonts"
            else:
                raise NotImplementedError("Font selection not implemented for other OS'")
        self.fonts_dir = fonts_dir
        self.items = [x for x in os.listdir(fonts_dir) if not x.endswith(".fon")]  # fon types currently unsupported
        self.filtered_widgets: list[tuple[str, tk.Label]] = []

        self.selection_tuple: tuple[str, tk.Label] | None = None
        self.selection: str | None = None
        self.normal_style = {"bg": "SystemButtonFace", "fg": "black"}
        self.selected_style = {"bg": "#0a64ad", "fg": "white"}
        self.hover_style = {"bg": "#e6f2ff"}
        self.preview_font_size: int = 20

        self._build_ui()
        self._create_widgets()

        self.top.wait_window()

    def _build_ui(self) -> None:
        # Search field
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._update_list)

        search_entry = ttk.Entry(self.top, textvariable=self.search_var)
        search_entry.pack(fill="x", padx=5, pady=5)

        scroll_frame = ttk.Frame(self.top)
        scroll_frame.pack(side="top", fill="both", expand=True)

        # Scrollable area
        self.canvas = tk.Canvas(scroll_frame, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        # update scrollregion when the contents change
        self.scrollable_frame.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.window_id, width=e.width))

        # enable mouse wheel scrolling (Windows/Mac/Linux) - bind to WINDOW, not globally
        self.top.bind("<MouseWheel>", self._on_mousewheel)
        self.top.bind("<Button-4>", self._on_mousewheel)
        self.top.bind("<Button-5>", self._on_mousewheel)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        ttk.Separator(self.top, orient="horizontal").pack(expand=True, fill="x")

        # font preview
        preview_frame = ttk.Frame(self.top)
        preview_frame.pack(fill="both", expand=True)
        ttk.Label(preview_frame, text="Preview font:").pack(anchor="nw")
        self.preview_font = ttk.Label(preview_frame, text="No font selected")
        self.preview_font.pack(anchor="nw")
        ttk.Button(self.top, text="Confirm", command=self._on_confirm).pack()

    def _create_widgets(self) -> None:
        for item in self.items:
            label = tk.Label(self.scrollable_frame, text=item, anchor="nw")
            label.bind("<Button-1>", lambda _event, text=item, widget=label: self._on_item_click(text, widget))  # type:ignore
            label.bind("<Enter>", self.on_enter)
            label.bind("<Leave>", self.on_leave)
            self.filtered_widgets.append((item, label))
        self._update_list()

    def _on_mousewheel(self, event: Any) -> None:
        # cross-platform mousewheel support
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")

    def _on_item_click(self, item: str, widget: tk.Label) -> None:
        self.selection_tuple = (item, widget)
        self._update_list()
        self._update_preview()

    def _on_confirm(self) -> None:
        if self.selection_tuple:
            self.selection = self.selection_tuple[0]
        self.top.destroy()

    def _on_cancel(self) -> None:
        self.top.destroy()

    def on_enter(self, event: tk.Event) -> None:
        if not self.selection_tuple or event.widget != self.selection_tuple[1]:
            event.widget.configure(**self.hover_style)

    def on_leave(self, event: tk.Event) -> None:
        if not self.selection_tuple or event.widget != self.selection_tuple[1]:
            event.widget.configure(**self.normal_style)

    def _update_list(self, *_args: Any) -> None:
        query = self.search_var.get().lower()

        self.filtered_widgets = sorted(self.filtered_widgets)
        for text, widget in self.filtered_widgets:
            widget.pack_forget()
            if query in text.lower():
                widget.pack(fill="x", anchor="w")
                if self.selection_tuple == (text, widget):
                    widget.config(**self.selected_style)
                else:
                    widget.config(**self.normal_style)
        self.canvas.yview_moveto(0)

    # def fake_custom_font(self, filepath:str) -> None:

    def _update_preview(self, *_args: Any) -> None:
        if self.selection_tuple and self.selection_tuple[0]:
            font_path = os.path.join(self.fonts_dir, self.selection_tuple[0])
            fake_font = create_fake_font(self.top, font_path, self.preview_font_size)

            self.preview_font.configure(font=fake_font, text="Sphinx of black quartz,\njudge my vow")
