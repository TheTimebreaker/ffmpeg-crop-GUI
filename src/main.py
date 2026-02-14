import atexit
import os
import random
import shlex
import string
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Literal, cast

from fontTools.ttLib import TTFont  # type:ignore
from send2trash import send2trash
from tkinterdnd2 import TkinterDnD

import common
import filters
import gui_vars
import media_info
from tabs import inout, croptrim


def printable_command(cmd: list[str]) -> str:
    if sys.platform == "win32":
        return subprocess.list2cmdline(cmd)
    else:
        return shlex.join(cmd)


def ffmpeg_drawtext_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("%", "%%").replace("'", "\\'")


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


def swap_list_indices(original_list: list[Any], index_a: int, index_b: int) -> list[Any]:
    original_list[index_a], original_list[index_b] = original_list[index_b], original_list[index_a]
    return original_list


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


class GUI:
    padx = 5
    pady = 5

    def __init__(self, root: TkinterDnD.Tk, vars: gui_vars.GuiVars) -> None:
        self.root = root
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.title("FFmpeg Crop GUI")
        self.root.minsize(800, 0)
        self.root.resizable(True, False)

        self.cleanup_files: list[Path] = []

        self.gui_vars: gui_vars.GuiVars = vars
        self.video_filter_args: list[tuple[filters.FiltersLiteral, dict[str, str]]] = []

        self.label_width = 15  # TODO enforce
        self.max_volume: float = 0.0

        self._build_ui()

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.inout = inout.InOut(self.notebook, parent=self, root=self.root, gui_vars=self.gui_vars)
        self.notebook.add(self.inout, text="Input / Output")

        self.tab_crop = croptrim.CropTrim(self.notebook, parent=self, root=self.root, gui_vars=self.gui_vars)
        self.notebook.add(self.tab_crop, text="Crop / Trim")

        self.tab_text = self._tab_addvideofilter(self.notebook)
        self.notebook.add(self.tab_text, text="Video Filters")

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", expand=True, padx=self.padx, pady=self.pady)
        self.process_button = ttk.Button(
            self.root,
            text="Process",
            command=self.process,
        )
        self.process_button.pack(fill="x", expand=True, padx=self.padx, pady=self.pady)

    def swap_videofilter_args(self, index_a: int, index_b: int) -> None:
        swap_list_indices(self.video_filter_args, index_a, index_b)
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

    def _tab_addvideofilter(self, root: TkinterDnD.Tk | ttk.Notebook) -> ttk.Frame:

        tab = ttk.Frame(root)
        tab.columnconfigure(0, weight=0)
        tab.columnconfigure(1, weight=0)
        tab.columnconfigure(2, weight=1)

        ttk.Label(tab, text="Video filter").grid(row=0, column=0, padx=self.padx, pady=self.pady, sticky="ew")
        self.selected_videofilter_var = tk.StringVar(tab)  # TODO add to central dict
        ttk.Combobox(tab, values=[*filters.SUPPORTED_FILTERS], textvariable=self.selected_videofilter_var).grid(
            row=0, column=1, padx=self.padx, pady=self.pady, sticky="new"
        )
        ttk.Button(tab, text="Add selected filter", command=self.addvideofilter_dialog).grid(
            row=1, column=0, columnspan=2, padx=self.padx, pady=self.pady, sticky="new"
        )

        hover = ttk.Label(tab, text="Hover here for additional info...")
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

        self.videofilter_filters_frame = ttk.Frame(tab)
        self.videofilter_filters_frame.grid(row=0, column=2, rowspan=2, sticky="nsew")
        self.videofilter_filters_frame.columnconfigure(0, weight=0)
        self.videofilter_filters_frame.columnconfigure(1, weight=0)
        self.videofilter_filters_frame.columnconfigure(2, weight=1)
        self.videofilter_filters_frame.columnconfigure(3, weight=0)
        self.videofilter_filters_frame.columnconfigure(4, weight=0)

        tab.grid_rowconfigure(3, weight=1)  # spacer
        ttk.Separator(tab, orient="horizontal").grid(row=4, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)
        self.process_button = ttk.Button(
            tab,
            text="Process",
            command=self.process,
        )
        self.process_button.grid(row=5, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)

        return tab

    def _reset_to_defaults(self) -> None:
        self.gui_vars.reset_settings_to_default()
        self.inout.update_codec_frames()
        self.video_filter_args = []  # TODO work this into the settings dict
        self.update_videofilter_preview()
        # TODO: work crop/trim into settings dict

    def get_timestamps(self) -> tuple[media_info.Timestamp, media_info.Timestamp] | Literal[False]:
        def validate_timestamp(
            hh: str | int | None,
            mm: str | int | None,
            ss: str | int | None,
            ms: str | int | None,
        ) -> media_info.Timestamp:
            if hh is not None and mm is not None and ss is not None and ms is not None:
                return media_info.Timestamp(int(hh), int(mm), int(ss), int(ms))
            raise TypeError()

        def get_timestamp_start() -> media_info.Timestamp:
            hh: str | int | None = self.gui_vars.settings["trim"]["hh_start"]["var"].get()
            mm: str | int | None = self.gui_vars.settings["trim"]["mm_start"]["var"].get()
            ss: str | int | None = self.gui_vars.settings["trim"]["ss_start"]["var"].get()
            ms: str | int | None = self.gui_vars.settings["trim"]["ms_start"]["var"].get()

            return validate_timestamp(hh, mm, ss, ms)

        def get_timestamp_end() -> media_info.Timestamp:
            hh: str | int | None = self.gui_vars.settings["trim"]["hh_end"]["var"].get()
            mm: str | int | None = self.gui_vars.settings["trim"]["mm_end"]["var"].get()
            ss: str | int | None = self.gui_vars.settings["trim"]["ss_end"]["var"].get()
            ms: str | int | None = self.gui_vars.settings["trim"]["ms_end"]["var"].get()

            return validate_timestamp(hh, mm, ss, ms)

        try:
            start = get_timestamp_start()
            end = get_timestamp_end()
        except ValueError:
            messagebox.showerror("Invalid timestamps", message="Your timestamp data is invalid! Remember to only put in NUMBERS.")
            return False
        return start, end

    def get_crop(self) -> tuple[int, int, int, int] | Literal[False]:
        try:
            width = self.gui_vars.settings["crop"]["width"]["var"].get()
            height = self.gui_vars.settings["crop"]["height"]["var"].get()
            left_top_x = self.gui_vars.settings["crop"]["left_top_x"]["var"].get()
            left_top_y = self.gui_vars.settings["crop"]["left_top_y"]["var"].get()
            return width, height, left_top_x, left_top_y
        except tk.TclError:
            messagebox.showerror("Invalid CROP values", "Your crop data is invalid! Remember to only put in NUMBERS.")
            return False

    def get_encoder_args_video_libx264(self) -> list[str]:
        args: list[str] = ["-c:v", "libx264"]

        # crf
        crf_default: int = self.gui_vars.settings["libx264"]["crf"]["default"]
        crf_selection: int = self.gui_vars.settings["libx264"]["crf"]["var"].get()
        if crf_default != crf_selection:
            args.append("-crf")
            args.append(str(crf_selection))

        # preset
        preset_default: str = self.gui_vars.settings["libx264"]["preset"]["default"]
        preset_selection: str = self.gui_vars.settings["libx264"]["preset"]["var"].get()
        if preset_default != preset_selection:
            args.append("-preset")
            args.append(preset_selection)

        # tune
        tune_default: str = self.gui_vars.settings["libx264"]["tune"]["default"]
        tune_selection: str = self.gui_vars.settings["libx264"]["tune"]["var"].get()
        if tune_default != tune_selection:
            args.append("-tune")
            args.append(tune_selection)

        return args

    def get_encoder_args_video_libx265(self) -> list[str]:
        args: list[str] = ["-c:v", "libx265"]

        # crf
        crf_default: int = self.gui_vars.settings["libx265"]["crf"]["default"]
        crf_selection: int = self.gui_vars.settings["libx265"]["crf"]["var"].get()
        if crf_default != crf_selection:
            args.append("-crf")
            args.append(str(crf_selection))

        # preset
        preset_default: str = self.gui_vars.settings["libx265"]["preset"]["default"]
        preset_selection: str = self.gui_vars.settings["libx265"]["preset"]["var"].get()
        if preset_default != preset_selection:
            args.append("-preset")
            args.append(preset_selection)

        # tune
        tune_default: str = self.gui_vars.settings["libx265"]["tune"]["default"]
        tune_selection: str = self.gui_vars.settings["libx265"]["tune"]["var"].get()
        if tune_default != tune_selection:
            args.append("-tune")
            args.append(tune_selection)

        return args

    def get_encoder_args_video(self) -> list[str]:
        selected_encoder = self.gui_vars.settings["general"]["selected_encoder_video"]["var"].get()
        match selected_encoder:
            case "libx264":
                return self.get_encoder_args_video_libx264()
            case "libx265":
                return self.get_encoder_args_video_libx265()
            case _:
                raise NotImplementedError("Encoder %s not implemented yet", selected_encoder)
        raise NotImplementedError("Encoder %s not implemented yet", selected_encoder)

    def get_video_filter_args(self) -> list[str]:
        entry_strs = []
        for filter, individual_call in self.video_filter_args:
            entry_args = []
            for i, (arg_name, arg_val) in enumerate(individual_call.items()):
                if filter == "drawtext" and arg_name == "text":  # workaround for newline characters.
                    tmppath = Path(f"ffmpeg_text_tempfile_{i}.txt").resolve()
                    self.cleanup_files.append(tmppath)
                    with open(tmppath, encoding="utf-8", mode="w") as f:
                        f.write(arg_val.replace("\\n", "\n"))

                    entry_args.append(f"textfile='{ffmpeg_drawtext_escape(str(tmppath))}'")
                else:
                    entry_args.append(f"{arg_name}='{ffmpeg_drawtext_escape(arg_val)}'")
            entry_strs.append(f"{filter}={':'.join(entry_args)}")
        print(entry_strs)
        return entry_strs

    def process(self) -> None:
        file: str = self.gui_vars.settings["general"]["file"]["var"].get()
        if not file or file == self.gui_vars.settings["general"]["file"]["default"]:
            messagebox.showerror("No file selected", message="You haven't selected a file to convert.")
            return

        timestamps = self.get_timestamps()
        if timestamps is False:
            return
        timestamp_start, timestamp_end = timestamps

        crops = self.get_crop()
        if crops is False:
            return
        width, height, left_top_x, left_top_y = crops

        video_copy: bool = not self.gui_vars.settings["general"]["force_reencoding_video"]["var"].get()
        audio_copy = True
        cmd = [
            "ffmpeg",
            "-i",
            file,
            "-y",  # overwrite always
        ]

        # trim / timestamp command
        if self.gui_vars.settings["trim"]["trim_enabled"]["var"].get():
            if timestamp_start and timestamp_start != media_info.Timestamp(0, 0, 0, 0):
                cmd.append("-ss")
                cmd.append(str(timestamp_start))
                video_copy = False
            if timestamp_end and timestamp_end != media_info.Timestamp(
                self.gui_vars.settings["trim"]["original_hh_end"]["var"].get(),
                self.gui_vars.settings["trim"]["original_mm_end"]["var"].get(),
                self.gui_vars.settings["trim"]["original_ss_end"]["var"].get(),
                self.gui_vars.settings["trim"]["original_ms_end"]["var"].get(),
            ):
                cmd.append("-to")
                cmd.append(str(timestamp_end))
                video_copy = False

        # Video filters
        video_filters = []
        # crop command
        if self.gui_vars.settings["crop"]["crop_enabled"]["var"].get() and (
            width != self.gui_vars.settings["crop"]["original_width"]["var"].get()
            or height != self.gui_vars.settings["crop"]["original_height"]["var"].get()
            or left_top_x != self.gui_vars.settings["crop"]["original_left_top_x"]["var"].get()
            or left_top_y != self.gui_vars.settings["crop"]["original_left_top_y"]["var"].get()
        ):
            video_filters.append(f"crop={width}:{height}:{left_top_x}:{left_top_y}")
            video_copy = False
        # Generic filters
        if self.video_filter_args:
            video_filters += self.get_video_filter_args()
            video_copy = False
        # Apply filters
        if video_filters:
            cmd.append("-filter:v")
            cmd.append(",".join(video_filters))

        # Audio filters
        # normalization
        if self.gui_vars.settings["general"]["normalize_audio"]["var"].get():
            cmd.append("-filter:a")
            cmd.append(f"volume={-1 * self.max_volume - 1}dB")
            audio_copy = False

        # COPYING CODECS
        if video_copy:
            cmd.append("-c:v")
            cmd.append("copy")
        else:
            cmd += self.get_encoder_args_video()
        if audio_copy:
            cmd.append("-c:a")
            cmd.append("copy")

        # output filename
        cmd.append(".".join(file.split(".")[0:-1]) + "-cropped." + file.split(".")[-1])

        print(cmd, printable_command(cmd))
        if sys.platform == "win32":
            subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(cmd, shell=True)

    def on_close(self) -> None:
        self.root.destroy()


def cleanup(g: GUI) -> None:
    for file in g.cleanup_files:
        try:
            send2trash(file)
        except Exception:
            print(f"An exception occurred while trying to delete file {file}")


def main() -> None:
    root = TkinterDnD.Tk()

    v = gui_vars.GuiVars(root)
    g = GUI(root, v)

    atexit.register(cleanup, g)
    root.mainloop()


if __name__ == "__main__":
    main()
