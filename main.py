import datetime
import json
import logging
import os
import random
import re
import shlex
import string
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Any, Final, Literal, cast, overload

from fontTools.ttLib import TTFont  # type:ignore
from tkinterdnd2 import DND_FILES, TkinterDnD

import filters


def printable_command(cmd: list[str]) -> str:
    if sys.platform == "win32":
        return subprocess.list2cmdline(cmd)
    else:
        return shlex.join(cmd)


def ffmpeg_drawtext_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("%", "%%").replace("'", "\\'")


def get_font_family(font_path: str) -> str:
    font_obj = TTFont(font_path)
    # 'name' table contains family and other name records
    for record in font_obj["name"].names:
        # Name ID 1 is the font family
        if record.nameID == 1:
            # Decode depending on platform
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


class Timestamp:
    @overload
    def __init__(self, duration: float) -> None: ...

    @overload
    def __init__(self, hh: int | None, mm: int | None, ss: int | None, ms: int | None) -> None: ...
    def __init__(self, *args: Any, **_: Any) -> None:
        if len(args) == 1:
            duration: float = args[0]
            delta = datetime.timedelta(seconds=duration)
            logging.info("Duration %s - delta %s", duration, delta)
            hh = int(str(delta).split(":")[0])
            mm = int(str(delta).split(":")[1])
            ss = int(str(delta).split(":")[2].split(".")[0])
            try:
                ms = int(str(delta).split(":")[2].split(".")[1][0:3])
            except IndexError as error:
                if "." not in str(delta).split(":")[2]:
                    ms = 0
                else:
                    raise IndexError from error
            self.hh: int | None = hh
            self.mm: int | None = mm
            self.ss: int | None = ss
            self.ms: int | None = ms

        elif len(args) == 4:
            hh, mm, ss, ms = args
            self.hh = hh
            self.mm = mm
            self.ss = ss
            self.ms = ms

    def __bool__(self) -> bool:
        return all(value is not None for value in [self.hh, self.mm, self.ss, self.ms])

    def __str__(self) -> str:
        if not self.__bool__():
            raise TypeError("Could not convert Timestamp to string due to some values being None.")
        return f"{str(self.hh).zfill(2)}:{str(self.mm).zfill(2)}:{str(self.ss).zfill(2)}.{str(self.ms).zfill(3)}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Timestamp):
            raise NotImplementedError
        return self.hh == other.hh and self.mm == other.mm and self.ss == other.ss and self.ms == other.ms


@dataclass
class VideoInfo:
    width: int
    height: int
    duration: Timestamp
    max_volume: float


def get_video_info(path: str) -> VideoInfo:
    def get_whd(path: str) -> tuple[int, int, Timestamp]:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            path,
        ]

        result = subprocess.run(cmd, **subprocess_kwargs)  # type:ignore # necessary because mypy is stupid with overloads
        data = json.loads(result.stdout)

        stream = data["streams"][0]

        width = int(stream["width"])
        height = int(stream["height"])

        # Duration: stream duration may be missing → fall back to format duration
        duration = float(stream.get("duration", data["format"]["duration"]))
        logging.info("duration: %s", duration)

        return width, height, Timestamp(duration)

    def get_max_volume(path: str) -> float:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-loglevel",
            "info",
            "-i",
            path,
            "-map",
            "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-filter:a",
            "volumedetect",
            "-f",
            "null",
            "NUL",
        ]

        logging.info(" ".join(cmd))
        result = subprocess.run(cmd, **subprocess_kwargs)  # type:ignore # necessary because mypy is stupid with overloads
        string = result.stderr
        logging.debug(string)
        for line in string.split("\n"):
            if all(s in line for s in ("Parsed_volumedetect", "max_volume")):
                regex = re.search(r"max_volume: (\-?[\d]{1,5}\.[\d]{1}) dB", line)
                if not regex:
                    raise ValueError("Cannot determine max_volume for this file...")
                max_volume = float(regex.group(1))
                return max_volume
        raise ValueError("Cannot determine max_volume for this file...")

    subprocess_kwargs: dict[str, int | bool] = dict(
        capture_output=True,
        text=True,
        check=True,
    )
    if sys.platform == "win32":
        subprocess_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # supresses new window creation

    width, height, duration = get_whd(path)
    max_volume = get_max_volume(path)

    return VideoInfo(
        width=width,
        height=height,
        duration=duration,
        max_volume=max_volume,
    )


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

    def __init__(self, root: TkinterDnD.Tk) -> None:
        self.root = root
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.title("FFmpeg Crop GUI")
        self.root.minsize(800, 0)
        self.root.resizable(True, False)

        self.CODECS_VIDEO: Final = (  # pylint:disable=C0103
            "libx264",
            "libx265",
        )
        self.codec_settings: dict[str, dict] = {  # type:ignore
            "general": {
                "file": {
                    "default": "Double click here or Drag & drop file ...",
                    "var": tk.StringVar(root),
                },
                "force_reencoding_video": {
                    "default": False,
                    "var": tk.BooleanVar(self.root),
                },
                "selected_encoder_video": {
                    "default": "libx264",
                    "var": tk.StringVar(self.root),
                },
                "crop_enabled": {
                    "default": True,
                    "var": tk.BooleanVar(self.root),
                },
                "trim_enabled": {
                    "default": True,
                    "var": tk.BooleanVar(self.root),
                },
            },
            "libx264": {
                "crf": {
                    "default": 23,
                    "var": tk.IntVar(self.root),
                },
                "preset": {
                    "default": "medium",
                    "var": tk.StringVar(self.root),
                },
                "tune": {
                    "default": "DEFAULT",
                    "var": tk.StringVar(self.root),
                },
            },
            "libx265": {
                "crf": {
                    "default": 28,
                    "var": tk.IntVar(self.root),
                },
                "preset": {
                    "default": "medium",
                    "var": tk.StringVar(self.root),
                },
                "tune": {
                    "default": "DEFAULT",
                    "var": tk.StringVar(self.root),
                },
            },
        }
        self.reset_settings_to_default()
        self.video_filter_args: dict[filters.FiltersLiteral, list[dict[str, str]]] = {}

        self.label_width = 15
        self.max_volume: float = 0.0

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.tab_input = self._tab_inout(self.notebook)
        self.notebook.add(self.tab_input, text="Input / Output")

        self.tab_crop = self._tab_crop_trim(self.notebook)
        self.notebook.add(self.tab_crop, text="Crop / Trim")

        self.tab_text = self._tab_addvideofilter(self.notebook)
        self.notebook.add(self.tab_text, text="Video Filters")

    def reset_settings_to_default(self) -> None:
        for section in self.codec_settings.values():
            for option in section.values():
                var = option.get("var")
                default = option.get("default")
                if var is not None and default is not None:
                    var.set(default)

    def _init_codec_frames(self) -> None:
        def _libx264() -> ttk.LabelFrame:
            f = ttk.LabelFrame(self.codec_options_frame, text="libx264 options")
            f.columnconfigure(0, weight=0)
            f.columnconfigure(1, weight=1)

            # CRF
            crf = ttk.Label(f, text="CRF")
            crf.grid(row=0, column=0, sticky="w", padx=self.padx, pady=self.pady)
            ToolTip(
                crf,
                "\n".join(
                    [
                        "Constant Rate Factor",
                        "Lower = less compression but larger filesize",
                        "Higher = more compression but smaller filesize",
                        "0: lossless for 8bit video and basically lossless for 10bit",
                        "17-18: visually lossless (the output should look the same even though it is technically compressed lossy)",
                        "23: Default value",
                        "51: Worst possible quality",
                    ]
                ),
            )
            tk.Scale(f, from_=0, to=51, variable=self.codec_settings["libx264"]["crf"]["var"], showvalue=True, orient="horizontal").grid(
                row=0, column=1, sticky="ew", padx=self.padx, pady=self.pady
            )

            # Preset
            preset = ttk.Label(f, text="Preset")
            preset.grid(row=1, column=0, sticky="w", padx=self.padx, pady=self.pady)
            ToolTip(
                preset,
                "\n".join(
                    [
                        "Determines the general speed of the process (sorted Fastest > Slowest)",
                        "If you target a certain filesize or constant bitrate you will receive higher quality with slower presets.",
                        "Default: medium",
                        "Placebo is basically useless, since it gives miniscule returns for vastly longer encoding times",
                    ]
                ),
            )
            ttk.Combobox(
                f,
                textvariable=self.codec_settings["libx264"]["preset"]["var"],
                values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo"],
                state="readonly",
            ).grid(row=1, column=1, sticky="ew", padx=self.padx, pady=self.pady)

            # Tune
            tune = ttk.Label(f, text="Tune")
            tune.grid(row=2, column=0, sticky="w", padx=self.padx, pady=self.pady)
            ToolTip(
                tune,
                "\n".join(
                    [
                        "Specifying a tune will make the encoder target certain types of content better.",
                        "film: use for high quality movie content; lowers deblocking",
                        "animation: good for cartoons; uses higher deblocking and more reference frames",
                        "grain: preserves the grain structure in old, grainy film material",
                        "stillimage: good for slideshow-like content",
                        "fastdecode: allows faster decoding by disabling certain filters",
                        "zerolatency: good for fast encoding and low-latency streaming",
                        "<Source: Official documentation>",
                    ]
                ),
            )
            ttk.Combobox(
                f,
                textvariable=self.codec_settings["libx264"]["tune"]["var"],
                values=["DEFAULT", "film", "animation", "grain", "stillimage", "fastdecode", "zerolatency"],
                state="readonly",
            ).grid(row=2, column=1, sticky="ew", padx=self.padx, pady=self.pady)

            return f

        def _libx265() -> ttk.LabelFrame:
            f = ttk.LabelFrame(self.codec_options_frame, text="libx265 options")
            f.columnconfigure(0, weight=0)
            f.columnconfigure(1, weight=1)

            # CRF
            crf = ttk.Label(f, text="CRF")
            crf.grid(row=0, column=0, sticky="w", padx=self.padx, pady=self.pady)
            ToolTip(
                crf,
                "\n".join(
                    [
                        "Constant Rate Factor",
                        "Lower = less compression but larger filesize",
                        "Higher = more compression but smaller filesize",
                        "28: Default. Visually equal to libx264's default (crf 23), but half the file size)",
                        "51: Worst possible quality",
                    ]
                ),
            )
            tk.Scale(f, from_=0, to=51, variable=self.codec_settings["libx265"]["crf"]["var"], showvalue=True, orient="horizontal").grid(
                row=0, column=1, sticky="ew", padx=self.padx, pady=self.pady
            )

            # Preset
            preset = ttk.Label(f, text="Preset")
            preset.grid(row=1, column=0, sticky="w", padx=self.padx, pady=self.pady)
            ToolTip(
                preset,
                "\n".join(
                    [
                        "Determines the general speed of the process (sorted Fastest > Slowest)",
                        "If you target a certain filesize or constant bitrate you will receive higher quality with slower presets.",
                        "Default: medium",
                        "Placebo is basically useless, since it gives miniscule returns for vastly longer encoding times",
                    ]
                ),
            )
            ttk.Combobox(
                f,
                textvariable=self.codec_settings["libx265"]["preset"]["var"],
                values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo"],
                state="readonly",
            ).grid(row=1, column=1, sticky="ew", padx=self.padx, pady=self.pady)

            # Tune
            tune = ttk.Label(f, text="Tune")
            tune.grid(row=2, column=0, sticky="w", padx=self.padx, pady=self.pady)
            ToolTip(
                tune,
                "\n".join(
                    [
                        "Specifying a tune will make the encoder target certain types of content better.",
                        "grain: preserves the grain structure in old, grainy film material",
                        "fastdecode: allows faster decoding by disabling certain filters",
                        "zerolatency: good for fast encoding and low-latency streaming",
                        "<Source: Official documentation>",
                    ]
                ),
            )
            ttk.Combobox(
                f,
                textvariable=self.codec_settings["libx265"]["tune"]["var"],
                values=["DEFAULT", "grain", "fastdecode", "zerolatency"],
                state="readonly",
            ).grid(row=2, column=1, sticky="ew", padx=self.padx, pady=self.pady)

            return f

        self.codec_options_frames: dict[str, ttk.Frame | ttk.LabelFrame] = {
            "libx264": _libx264(),
            "libx265": _libx265(),
        }

    def update_codec_frames(self, _: Any = None) -> None:
        for val in self.codec_options_frames.values():
            val.forget()
        selected_encoder = self.codec_settings["general"]["selected_encoder_video"]["var"].get()
        self.codec_options_frames[selected_encoder].pack(expand=True, fill="both")

    def _tab_inout(self, root: TkinterDnD.Tk | ttk.Notebook) -> ttk.Frame:
        tab = ttk.Frame(root)

        tab.columnconfigure(0, weight=0)
        tab.columnconfigure(1, weight=1)

        self.file_source_label = ttk.Label(
            tab,
            text="Source file",
        )
        self.file_source_label.grid(row=0, column=0, sticky="ew", padx=self.padx, pady=self.pady)

        self.downloadlocation_entry = ttk.Label(
            tab,
            textvariable=self.codec_settings["general"]["file"]["var"],
        )
        self.downloadlocation_entry.grid(row=0, column=1, sticky="ew", padx=self.padx, pady=self.pady)

        tab.drop_target_register(DND_FILES)  # type:ignore
        tab.dnd_bind(  # type:ignore
            "<<Drop>>",
            self.set_file_ondrop,
        )
        self.downloadlocation_entry.bind("<Double-Button-1>", self.set_file_dialogue)

        ttk.Separator(tab, orient="horizontal").grid(row=6, column=0, columnspan=2, sticky="ew", padx=self.padx, pady=self.pady)

        ttk.Label(
            tab,
            text="Additional settings",
        ).grid(row=7, column=0, sticky="ew", padx=self.padx, pady=self.pady)

        self.autonormalize_var = tk.BooleanVar(tab, True)
        self.autonormalize_btn = ttk.Checkbutton(
            tab,
            text="Automatically normalize audio to -1.0 dB",
            variable=self.autonormalize_var,
        )
        self.autonormalize_btn.grid(row=7, column=1, sticky="ew", padx=self.padx, pady=self.pady)

        ttk.Separator(tab, orient="horizontal").grid(row=8, column=0, columnspan=2, sticky="ew", padx=self.padx, pady=self.pady)
        video_encoder_label = ttk.Label(tab, text="Video encoder\n(if needed)")
        video_encoder_label.grid(row=9, column=0, sticky="ew", padx=self.padx, pady=self.pady)
        ToolTip(
            video_encoder_label,
            "\n".join(
                [
                    "This tool will attempt to copy the video feed if possible and",
                    "only reencode the video with settings selected here if needed.",
                    "Settings that require reencoding include cropping and trimming.",
                ]
            ),
        )
        ttk.Checkbutton(tab, text="Force reencoding", variable=self.codec_settings["general"]["force_reencoding_video"]["var"]).grid(
            row=9, column=1, padx=self.padx, pady=self.pady, sticky="ew"
        )
        encoder = ttk.Combobox(
            tab, textvariable=self.codec_settings["general"]["selected_encoder_video"]["var"], values=self.CODECS_VIDEO, state="readonly"
        )
        encoder.grid(sticky="ew", row=10, column=1, padx=self.padx, pady=self.pady)
        encoder.bind("<<ComboboxSelected>>", self.update_codec_frames)

        self.codec_options_frame = ttk.Frame(tab)
        self.codec_options_frame.grid(row=11, column=1, sticky="ew", padx=self.padx, pady=self.pady)
        self._init_codec_frames()
        self.update_codec_frames(None)

        tab.grid_rowconfigure(12, weight=1)
        ttk.Separator(tab, orient="horizontal").grid(row=13, column=0, columnspan=2, sticky="ew", padx=self.padx, pady=self.pady)
        self.process_button = ttk.Button(
            tab,
            text="Process",
            command=self.process,
        )
        self.process_button.grid(row=14, column=0, columnspan=2, sticky="ew", padx=self.padx, pady=self.pady)

        return tab

    def _tab_crop_trim(self, root: TkinterDnD.Tk | ttk.Notebook) -> ttk.Frame:
        tab = ttk.Frame(root)
        tab.columnconfigure(0, weight=0)
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(2, weight=1)

        crop_enabled = ttk.Checkbutton(tab, variable=self.codec_settings["general"]["crop_enabled"]["var"], text="Enable Crop")
        crop_enabled.grid(row=0, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)
        ToolTip(
            crop_enabled,
            text="Allows the encoder to CROP the video with the settings specified here."
            "\nThe system is smart and will only actually crop if these values were changed from the original values.",
        )

        # Left top pixel
        ttk.Label(
            tab,
            text="Top left corner (X / Y)",
        ).grid(row=2, column=0, sticky="w", padx=self.padx, pady=self.pady)
        self.left_top_x = tk.IntVar(tab)
        self.left_top_y = tk.IntVar(tab)
        ttk.Spinbox(
            tab,
            textvariable=self.left_top_x,
            from_=0,
            to=50000,
        ).grid(row=2, column=1, sticky="ew", padx=self.padx, pady=self.pady)
        ttk.Spinbox(
            tab,
            textvariable=self.left_top_y,
            from_=0,
            to=50000,
        ).grid(row=2, column=2, sticky="ew", padx=self.padx, pady=self.pady)

        # Box Dimensions
        ttk.Label(
            tab,
            text="Box width (X / Y)",
        ).grid(row=3, column=0, sticky="w", padx=self.padx, pady=self.pady)
        self.width_x = tk.IntVar(tab)
        self.height_y = tk.IntVar(tab)
        ttk.Spinbox(
            tab,
            textvariable=self.width_x,
            from_=0,
            to=50000,
        ).grid(row=3, column=1, sticky="ew", padx=self.padx, pady=self.pady)
        ttk.Spinbox(
            tab,
            textvariable=self.height_y,
            from_=0,
            to=50000,
        ).grid(row=3, column=2, sticky="ew", padx=self.padx, pady=self.pady)

        ttk.Separator(tab, orient="horizontal").grid(row=4, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)

        # Trim
        trim_enabled = ttk.Checkbutton(tab, variable=self.codec_settings["general"]["trim_enabled"]["var"], text="Enable Trim")
        trim_enabled.grid(row=5, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)
        ToolTip(
            trim_enabled,
            text="Allows the encoder to TRIM the video with the settings specified here."
            "\nThe system is smart and will only actually crop if these values were changed from the original values.",
        )

        ttk.Label(
            tab,
            text="Timestamp Start (HH:MM:SS.MS)",
        ).grid(row=6, column=0, sticky="w", padx=self.padx, pady=self.pady)
        self.timestamp_start_frame = ttk.Frame(tab)
        self.timestamp_start_frame.grid(row=6, column=1, columnspan=2, sticky="ew", padx=self.padx, pady=self.pady)
        self.hh_start = ttk.Spinbox(self.timestamp_start_frame, from_=0, to=99, width=3, format="%02.0f")
        self.hh_start.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_start_frame, text=" : ").pack(side="left")
        self.mm_start = ttk.Spinbox(self.timestamp_start_frame, from_=0, to=59, width=3, format="%02.0f")
        self.mm_start.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_start_frame, text=" : ").pack(side="left")
        self.ss_start = ttk.Spinbox(self.timestamp_start_frame, from_=0, to=59, width=3, format="%02.0f")
        self.ss_start.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_start_frame, text=" . ").pack(side="left")
        self.ms_start = ttk.Spinbox(self.timestamp_start_frame, from_=0, to=999, width=4)
        self.ms_start.pack(side="left", fill="x", expand=True)

        # Timestamp End
        ttk.Label(
            tab,
            text="Timestamp End (HH:MM:SS.MS)",
        ).grid(row=7, column=0, sticky="w", padx=self.padx, pady=self.pady)
        self.timestamp_end_frame = ttk.Frame(tab)
        self.timestamp_end_frame.grid(row=7, column=1, columnspan=2, sticky="ew", padx=self.padx, pady=self.pady)
        self.hh_end = ttk.Spinbox(self.timestamp_end_frame, from_=0, to=99, width=3, format="%02.0f")
        self.hh_end.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_end_frame, text=" : ").pack(side="left")
        self.mm_end = ttk.Spinbox(self.timestamp_end_frame, from_=0, to=59, width=3, format="%02.0f")
        self.mm_end.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_end_frame, text=" : ").pack(side="left")
        self.ss_end = ttk.Spinbox(self.timestamp_end_frame, from_=0, to=59, width=3, format="%02.0f")
        self.ss_end.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_end_frame, text=" . ").pack(side="left")
        self.ms_end = ttk.Spinbox(self.timestamp_end_frame, from_=0, to=999, width=4)
        self.ms_end.pack(side="left", fill="x", expand=True)

        tab.grid_rowconfigure(8, weight=1)
        ttk.Separator(tab, orient="horizontal").grid(row=9, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)
        self.process_button = ttk.Button(
            tab,
            text="Process",
            command=self.process,
        )
        self.process_button.grid(row=10, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)

        return tab

    def update_videofilter_preview(self) -> None:
        for child in self.videofilter_filters_frame.winfo_children():
            child.destroy()

        row = 0
        for filter, entries in self.video_filter_args.items():
            print(filter, entries)
            for entry in entries:
                ttk.Label(self.videofilter_filters_frame, text=filter, justify="left").grid(
                    row=row,
                    column=0,
                    sticky="ew",
                    padx=self.padx,
                    pady=self.pady,
                )
                ttk.Label(self.videofilter_filters_frame, text=str(entry), justify="left").grid(
                    row=row,
                    column=1,
                    sticky="ew",
                    padx=self.padx,
                    pady=self.pady,
                )
                ttk.Button(
                    self.videofilter_filters_frame,
                    text="Edit",
                    command=lambda f=filter, e=entry: self.editvideofilter_dialog(f, e),  # type:ignore
                ).grid(row=row, column=2, sticky="ew", padx=self.padx, pady=self.pady)
                row += 1

    def addvideofilter_dialog(self, prefilled_args: dict[str, str] | None = None, replace_index: int | None = None) -> None:
        selected_filter = cast(filters.FiltersLiteral, self.selected_videofilter_var.get())
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
            if selected_filter not in self.video_filter_args:
                self.video_filter_args[selected_filter] = []
            if replace_index is not None:
                self.video_filter_args[selected_filter][replace_index] = dict(dialog.args)
            else:
                self.video_filter_args[selected_filter].append(dict(dialog.args))
        else:
            raise TypeError("No arguments returned...")
        self.update_videofilter_preview()

    def editvideofilter_dialog(self, filter: filters.FiltersLiteral, args_to_edit: dict[str, str]) -> None:
        for i, args_entry in enumerate(self.video_filter_args[filter]):
            if args_entry == args_to_edit:
                self.addvideofilter_dialog(args_to_edit, i)
                return

    def _tab_addvideofilter(self, root: TkinterDnD.Tk | ttk.Notebook) -> ttk.Frame:

        tab = ttk.Frame(root)
        tab.columnconfigure(0, weight=0)
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(2, weight=5)

        ttk.Label(tab, text="Video filter").grid(row=0, column=0, padx=self.padx, pady=self.pady, sticky="w")
        self.selected_videofilter_var = tk.StringVar(tab)  # TODO add to central dict
        ttk.Combobox(tab, values=[*filters.SUPPORTED_FILTERS], textvariable=self.selected_videofilter_var).grid(
            row=0, column=1, padx=self.padx, pady=self.pady, sticky="new"
        )
        ttk.Button(tab, text="Add selected filter", command=self.addvideofilter_dialog).grid(
            row=1, column=0, columnspan=2, padx=self.padx, pady=self.pady, sticky="new"
        )

        self.videofilter_filters_frame = ttk.Frame(tab)
        self.videofilter_filters_frame.grid(row=0, column=2, rowspan=2, sticky="nsew")
        self.videofilter_filters_frame.columnconfigure(0, weight=0)
        self.videofilter_filters_frame.columnconfigure(1, weight=1)
        self.videofilter_filters_frame.columnconfigure(2, weight=0)

        tab.grid_rowconfigure(1, weight=1)  # spacer
        ttk.Separator(tab, orient="horizontal").grid(row=2, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)
        self.process_button = ttk.Button(
            tab,
            text="Process",
            command=self.process,
        )
        self.process_button.grid(row=3, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)

        return tab

    def set_file_dialogue(self, _: Any) -> None:
        path = filedialog.askopenfilename()
        if path:
            self.set_file(path)

    def set_file_ondrop(self, event: Any) -> None:
        files = self.root.tk.splitlist(event.data)
        if files:
            self.set_file(files[0])

    def _reset_to_defaults(self) -> None:
        self.reset_settings_to_default()
        self.update_codec_frames()
        self.video_filter_args = {}  # TODO work this into the settings dict
        self.update_videofilter_preview()
        # TODO: work crop/trim into settings dict

    def set_file(self, path: str) -> None:
        self._reset_to_defaults()

        v = get_video_info(path)
        self.max_volume = v.max_volume
        self.codec_settings["general"]["file"]["var"].set(path)

        self.width_x.set(v.width)
        self.height_y.set(v.height)
        self.left_top_x.set(0)
        self.left_top_y.set(0)
        self.original_width = v.width
        self.original_height = v.height
        self.original_left_top_x = 0
        self.original_left_top_y = 0

        self.hh_start.set(0)
        self.mm_start.set(0)
        self.ss_start.set(0)
        self.ms_start.set(0)
        self.hh_end.set(v.duration.hh)
        self.mm_end.set(v.duration.mm)
        self.ss_end.set(v.duration.ss)
        self.ms_end.set(v.duration.ms)
        self.original_start = Timestamp(0, 0, 0, 0)
        self.original_end = Timestamp(v.duration.hh, v.duration.mm, v.duration.ss, v.duration.ms)

    def get_timestamps(self) -> tuple[Timestamp, Timestamp] | Literal[False]:
        def validate_timestamp(
            hh: str | int | None,
            mm: str | int | None,
            ss: str | int | None,
            ms: str | int | None,
        ) -> Timestamp:
            if hh is not None and mm is not None and ss is not None and ms is not None:
                return Timestamp(int(hh), int(mm), int(ss), int(ms))
            raise TypeError()

        def get_timestamp_start() -> Timestamp:
            hh: str | int | None = self.hh_start.get()
            mm: str | int | None = self.mm_start.get()
            ss: str | int | None = self.ss_start.get()
            ms: str | int | None = self.ms_start.get()

            return validate_timestamp(hh, mm, ss, ms)

        def get_timestamp_end() -> Timestamp:
            hh: str | int | None = self.hh_end.get()
            mm: str | int | None = self.mm_end.get()
            ss: str | int | None = self.ss_end.get()
            ms: str | int | None = self.ms_end.get()

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
            width = self.width_x.get()
            height = self.height_y.get()
            left_top_x = self.left_top_x.get()
            left_top_y = self.left_top_y.get()
            return width, height, left_top_x, left_top_y
        except tk.TclError:
            messagebox.showerror("Invalid CROP values", "Your crop data is invalid! Remember to only put in NUMBERS.")
            return False

    def get_encoder_args_video_libx264(self) -> list[str]:
        args: list[str] = ["-c:v", "libx264"]

        # crf
        crf_default: int = self.codec_settings["libx264"]["crf"]["default"]
        crf_selection: int = self.codec_settings["libx264"]["crf"]["var"].get()
        if crf_default != crf_selection:
            args.append("-crf")
            args.append(str(crf_selection))

        # preset
        preset_default: str = self.codec_settings["libx264"]["preset"]["default"]
        preset_selection: str = self.codec_settings["libx264"]["preset"]["var"].get()
        if preset_default != preset_selection:
            args.append("-preset")
            args.append(preset_selection)

        # tune
        tune_default: str = self.codec_settings["libx264"]["tune"]["default"]
        tune_selection: str = self.codec_settings["libx264"]["tune"]["var"].get()
        if tune_default != tune_selection:
            args.append("-tune")
            args.append(tune_selection)

        return args

    def get_encoder_args_video_libx265(self) -> list[str]:
        args: list[str] = ["-c:v", "libx265"]

        # crf
        crf_default: int = self.codec_settings["libx265"]["crf"]["default"]
        crf_selection: int = self.codec_settings["libx265"]["crf"]["var"].get()
        if crf_default != crf_selection:
            args.append("-crf")
            args.append(str(crf_selection))

        # preset
        preset_default: str = self.codec_settings["libx265"]["preset"]["default"]
        preset_selection: str = self.codec_settings["libx265"]["preset"]["var"].get()
        if preset_default != preset_selection:
            args.append("-preset")
            args.append(preset_selection)

        # tune
        tune_default: str = self.codec_settings["libx265"]["tune"]["default"]
        tune_selection: str = self.codec_settings["libx265"]["tune"]["var"].get()
        if tune_default != tune_selection:
            args.append("-tune")
            args.append(tune_selection)

        return args

    def get_encoder_args_video(self) -> list[str]:
        selected_encoder = self.codec_settings["general"]["selected_encoder_video"]["var"].get()
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
        for filter, args in self.video_filter_args.items():
            entry_args = []
            for entry in args:
                for arg_name, arg_val in entry.items():
                    entry_args.append(f"{arg_name}='{ffmpeg_drawtext_escape(arg_val)}'")
            entry_strs.append(f"{filter}={':'.join(entry_args)}")
        return entry_strs

    def process(self) -> None:
        file: str = self.codec_settings["general"]["file"]["var"].get()
        if not file or file == self.codec_settings["general"]["file"]["default"]:
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

        video_copy: bool = not self.codec_settings["general"]["force_reencoding_video"]["var"].get()
        audio_copy = True
        cmd = [
            "ffmpeg",
            "-i",
            file,
            "-y",  # overwrite always
        ]

        # trim / timestamp command
        if self.codec_settings["general"]["trim_enabled"]["var"].get():
            if timestamp_start and timestamp_start != self.original_start:
                cmd.append("-ss")
                cmd.append(str(timestamp_start))
                video_copy = False
            if timestamp_end and timestamp_end != self.original_end:
                cmd.append("-to")
                cmd.append(str(timestamp_end))
                video_copy = False

        # Video filters
        video_filters = []
        # crop command
        if self.codec_settings["general"]["crop_enabled"]["var"].get() and (
            width != self.original_width
            or height != self.original_height
            or left_top_x != self.original_left_top_x
            or left_top_y != self.original_left_top_y
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
        if self.autonormalize_var.get():
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

        print(printable_command(cmd))
        if sys.platform == "win32":
            subprocess.run(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run(cmd, shell=True)

    def on_close(self) -> None:
        self.root.destroy()


def main() -> None:
    root = TkinterDnD.Tk()
    GUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
