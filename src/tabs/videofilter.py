from __future__ import annotations

import os
import random
import string
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Any, cast

from fontTools.ttLib import TTFont  # type:ignore

import common
import filters
import gui_vars

if TYPE_CHECKING:
    from main import GUI


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


class SearchableFont:  # TODO: move font to its own thing
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


class FFmpegArgsDialog:
    def __init__(
        self,
        parent: tk.Tk,
        required_args: list[str] | None = None,
        optional_args: list[str] | None = None,
        prefilled_args: dict[str, str] | None = None,
    ) -> None:
        self.parent = parent
        self.top = tk.Toplevel(parent)
        self.top.title("Add FFmpeg Filter Arguments")
        self.top.grab_set()
        self.args: list[tuple[str, str]] = []

        self.required_args = required_args or []
        self.optional_args = optional_args or []
        self.arg_options = self.required_args + self.optional_args
        self.prefilled_args = prefilled_args or {}
        self.rows: list[tuple[tk.StringVar, tk.StringVar, int]] = []

        # Frame for table
        self.table_frame = tk.Frame(self.top)
        self.table_frame.pack(padx=10, pady=10)

        # Header
        tk.Label(self.table_frame, text="Argument").grid(row=0, column=0, padx=5)
        tk.Label(self.table_frame, text="Value").grid(row=0, column=1, padx=5)

        # Add initial row(s)
        if self.prefilled_args:
            for arg_name, arg_val in self.prefilled_args.items():
                self.add_row(arg_name, arg_val)
        else:
            self.add_row()

        # Buttons
        btn_frame = tk.Frame(self.top)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Add Row", command=self.add_row).pack(side="left", padx=5)
        tk.Button(btn_frame, text="OK", command=self.on_ok).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.on_cancel).pack(side="left", padx=5)

        self.top.wait_window()

    def _format_combobox_values(self) -> list[str]:
        """Format values with required args in bold (prefixed with ***)"""
        formatted = [f"*** {arg} ***" for arg in self.required_args]
        formatted.extend(self.optional_args)
        return formatted

    def _format_arg(self, arg: str) -> str:
        if arg in self.required_args:
            return f"*** {arg} ***"
        return arg

    def _extract_arg_name(self, formatted_arg: str) -> str:
        """Extract the actual argument name from formatted string"""
        if formatted_arg.startswith("*** ") and formatted_arg.endswith(" ***"):
            return formatted_arg[4:-4]
        return formatted_arg

    def _get_used_args(self) -> set[str]:
        """Get the set of arguments currently used in rows"""
        used = set()
        for arg_var, _, _ in self.rows:
            arg_str = arg_var.get()
            if arg_str:
                actual_arg = self._extract_arg_name(arg_str)
                used.add(actual_arg)
        return used

    def _get_available_options(self) -> list[str]:
        used_args = self._get_used_args()
        available_required = [f"*** {arg} ***" for arg in self.required_args if arg not in used_args]
        available_optional = [arg for arg in self.optional_args if arg not in used_args]
        return available_required + available_optional

    def _on_arg_selection_changed(self, *_args: Any) -> None:
        self.refresh_table()

    def _fontfile_selected_check(self, arg_var: tk.StringVar, value_var: tk.StringVar) -> None:
        arg_str = arg_var.get()
        actual_arg = self._extract_arg_name(arg_str) if arg_str else ""

        if actual_arg == "fontfile":
            dialog = SearchableFont(self.top)  # Claude: ignore this line
            if dialog.selection:
                value_var.set(os.path.join(dialog.fonts_dir, dialog.selection))

    def add_row(self, arg_name: str | None = None, value: str | None = None) -> None:
        row_index = len(self.rows) + 1
        formatted = self._format_arg(arg_name) if arg_name else ""
        arg_var = tk.StringVar(value=formatted)
        value_var = tk.StringVar(value=value or "")

        available_options = self._get_available_options()
        arg_cb = ttk.Combobox(self.table_frame, values=available_options, textvariable=arg_var, width=20)
        arg_cb.grid(row=row_index, column=0, padx=5, pady=2)
        value_entry = tk.Entry(self.table_frame, textvariable=value_var, width=20)
        value_entry.grid(row=row_index, column=1, padx=5, pady=2)
        delete_btn = tk.Button(self.table_frame, text="Remove", command=lambda: self.remove_row(row_index))
        delete_btn.grid(row=row_index, column=2, padx=5, pady=2)

        # Add trace to update combobox options when this argument changes
        arg_var.trace("w", self._on_arg_selection_changed)  # type:ignore

        # Add trace to handle fontfile special case
        arg_var.trace("w", lambda *_args: self._fontfile_selected_check(arg_var, value_var))  # type:ignore

        self.rows.append((arg_var, value_var, row_index))

    def remove_row(self, row_index: int) -> None:
        # Find and remove the row from self.rows
        self.rows = [(arg, value, idx) for arg, value, idx in self.rows if idx != row_index]

        # Remove widgets from grid
        for widget in self.table_frame.grid_slaves(row=row_index):
            widget.grid_forget()

        # Re-layout remaining rows
        self.refresh_table()

    def refresh_table(self) -> None:
        # Clear all rows except header
        for widget in self.table_frame.grid_slaves():
            if widget.grid_info()["row"] > 0:
                widget.grid_forget()

        # Re-grid all rows with available options (excluding used arguments)
        available_options = self._get_available_options()
        for idx, (arg_var, value_var, _) in enumerate(self.rows, start=1):
            arg_cb = ttk.Combobox(self.table_frame, values=available_options, textvariable=arg_var, width=20)
            arg_cb.grid(row=idx, column=0, padx=5, pady=2)
            value_entry = tk.Entry(self.table_frame, textvariable=value_var, width=20)
            value_entry.grid(row=idx, column=1, padx=5, pady=2)
            delete_btn = tk.Button(self.table_frame, text="Remove", command=lambda i=idx: self.remove_row(i))  # type:ignore
            delete_btn.grid(row=idx, column=2, padx=5, pady=2)

    def on_ok(self) -> None:
        # Extract actual argument names and build args list
        args_list = []
        added_args = set()

        for arg, value, _ in self.rows:
            arg_str = arg.get()
            if arg_str:
                actual_arg = self._extract_arg_name(arg_str)
                args_list.append((actual_arg, value.get()))
                added_args.add(actual_arg)

        # Check if all required arguments are present
        missing_args = [arg for arg in self.required_args if arg not in added_args]

        if missing_args:
            missing_str = ", ".join(missing_args)
            messagebox.showerror("Missing Required Arguments", f"The following required arguments are missing:\n\n{missing_str}")
            return

        self.args = args_list
        self.top.destroy()

    def on_cancel(self) -> None:
        self.top.destroy()


class Videofilter(ttk.Frame):
    padx = 5
    pady = 5

    def __init__(
        self,
        master: ttk.Notebook | None = None,
        *,
        border: Any | None = None,
        borderwidth: int | None = None,
        class_: Any = "",
        cursor: Any = "",
        height: int = 0,
        name: str | None = None,
        padding: int | None = None,
        relief: Any | None = None,
        style: Any = "",
        takefocus: Any = "",
        width: int = 0,
        parent: GUI,
        root: tk.Tk,
        gui_vars: gui_vars.GuiVars,
    ) -> None:
        super().__init__(
            master,
            border=border,
            borderwidth=borderwidth,
            class_=class_,
            cursor=cursor,
            height=height,
            name=name,
            padding=padding,
            relief=relief,
            style=style,
            takefocus=takefocus,
            width=width,
        )
        self.gui_vars = gui_vars
        self.parent = parent
        self.root = root

        self.video_filter_args: list[tuple[filters.FiltersLiteral, dict[str, str]]] = []

        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=0)
        self.columnconfigure(2, weight=1)

        ttk.Label(self, text="Video filter").grid(row=0, column=0, padx=self.padx, pady=self.pady, sticky="ew")
        self.selected_videofilter_var = tk.StringVar(self)  # TODO add to central dict
        ttk.Combobox(self, values=[*filters.SUPPORTED_FILTERS], textvariable=self.selected_videofilter_var).grid(
            row=0, column=1, padx=self.padx, pady=self.pady, sticky="new"
        )
        ttk.Button(self, text="Add selected filter", command=self.addvideofilter_dialog).grid(
            row=1, column=0, columnspan=2, padx=self.padx, pady=self.pady, sticky="new"
        )

        hover = ttk.Label(self, text="Hover here for additional info...")
        hover.grid(row=2, column=0, columnspan=2, padx=self.padx, pady=self.pady, sticky="w")
        common.ToolTip(
            hover,
            "FFmpeg's video filters are very deep!\n"
            "It is generally recommended to check the official documentation\n"
            "before using them here.\n\n"
            "Addtionally, this filter section does very little verification.\n"
            "This means that using filters incorrectly will let you run the\n"
            "command without it working properly.\n",
        )

        self.videofilter_filters_frame = ttk.Frame(self)
        self.videofilter_filters_frame.grid(row=0, column=2, rowspan=2, sticky="nsew")
        self.videofilter_filters_frame.columnconfigure(0, weight=0)
        self.videofilter_filters_frame.columnconfigure(1, weight=0)
        self.videofilter_filters_frame.columnconfigure(2, weight=1)
        self.videofilter_filters_frame.columnconfigure(3, weight=0)
        self.videofilter_filters_frame.columnconfigure(4, weight=0)

        return self

    def swap_videofilter_args(self, index_a: int, index_b: int) -> None:
        common.swap_list_indices(self.video_filter_args, index_a, index_b)
        self.update_videofilter_preview()

    def update_videofilter_preview(self) -> None:
        def up_button_state(row: int) -> str:
            if row == 0:
                return "disabled"
            return "normal"

        def down_button_state(row: int) -> str:
            if row == (len(self.video_filter_args) - 1):
                return "disabled"
            return "normal"

        for child in self.videofilter_filters_frame.winfo_children():
            child.destroy()

        row = 0
        for filter, entry in self.video_filter_args:
            button_frame = ttk.Frame(self.videofilter_filters_frame)
            button_frame.grid(row=row, column=0, sticky="ew", padx=self.padx, pady=self.pady)
            ttk.Button(
                button_frame,
                text="↑",
                width=2,
                state=up_button_state(row),
                command=lambda ia=row, ib=row - 1: self.swap_videofilter_args(ia, ib),  # type:ignore
            ).grid(row=0, column=0)
            ttk.Button(
                button_frame,
                text="↓",
                width=2,
                state=down_button_state(row),
                command=lambda ia=row, ib=row + 1: self.swap_videofilter_args(ia, ib),  # type:ignore
            ).grid(row=0, column=1)
            ttk.Label(self.videofilter_filters_frame, text=filter, justify="left").grid(
                row=row,
                column=1,
                sticky="ew",
                padx=self.padx,
                pady=self.pady,
            )
            mainlabel = ttk.Label(self.videofilter_filters_frame, text=str(entry), justify="left")  # TODO automatic wrapping
            mainlabel.grid(
                row=row,
                column=2,
                sticky="ew",
                padx=self.padx,
                pady=self.pady,
            )
            ttk.Button(
                self.videofilter_filters_frame,
                text="Edit",
                command=lambda f=filter, e=entry: self.editvideofilter_dialog(f, e),  # type:ignore
            ).grid(row=row, column=3, sticky="ew", padx=self.padx, pady=self.pady)
            ttk.Button(
                self.videofilter_filters_frame,
                text="Remove",
                command=lambda f=filter, e=entry: self.removevideofilter(f, e),  # type:ignore
            ).grid(row=row, column=4, sticky="ew", padx=self.padx, pady=self.pady)
            row += 1

    def addvideofilter_dialog(
        self, prefilled_args: dict[str, str] | None = None, replace_index: int | None = None, filter: filters.FiltersLiteral | None = None
    ) -> None:
        if filter is None:
            selected_filter = cast(filters.FiltersLiteral, self.selected_videofilter_var.get())
        else:
            selected_filter = cast(filters.FiltersLiteral, filter)
        selected_typeddict = filters.filtermap(selected_filter)
        required = list(selected_typeddict.__required_keys__)  # type:ignore
        optional = list(selected_typeddict.__optional_keys__)  # type:ignore

        dialog = FFmpegArgsDialog(
            self.root,
            required_args=required,
            optional_args=optional,
            prefilled_args=prefilled_args,
        )
        if dialog.args:
            if replace_index is not None:
                self.video_filter_args[replace_index] = (selected_filter, dict(dialog.args))
            else:
                self.video_filter_args.append((selected_filter, dict(dialog.args)))
        else:
            raise TypeError("No arguments returned...")
        self.update_videofilter_preview()

    def removevideofilter(self, filter_to_remove: filters.FiltersLiteral, args_to_remove: dict[str, str]) -> None:
        for entry in self.video_filter_args:
            if entry == (filter_to_remove, args_to_remove):
                self.video_filter_args.remove(entry)
                self.update_videofilter_preview()
                return

    def editvideofilter_dialog(self, filter_to_edit: filters.FiltersLiteral, args_to_edit: dict[str, str]) -> None:
        for i, (args_filter, args_entry) in enumerate(self.video_filter_args):
            if args_filter == filter_to_edit and args_entry == args_to_edit:
                self.addvideofilter_dialog(args_to_edit, replace_index=i, filter=filter_to_edit)
                return
