import tkinter as tk
from typing import TypedDict

import filters


class DefaultVarDict(TypedDict):
    default: str | int | bool
    var: tk.Variable


class GuiVars:
    settings: dict[str, dict[str, DefaultVarDict]]

    def __init__(self, root: tk.Tk) -> None:
        self.setup_settings(root)
        self.reset_settings_to_default()

    def setup_settings(self, root: tk.Tk) -> None:
        self.settings = {
            "general": {
                "file": {
                    "default": "Double click here or Drag & drop file ...",
                    "var": tk.StringVar(root),
                },
                "normalize_audio": {
                    "default": True,
                    "var": tk.BooleanVar(root),
                },
                "force_reencoding_video": {
                    "default": False,
                    "var": tk.BooleanVar(root),
                },
                "selected_encoder_video": {
                    "default": "libx264",
                    "var": tk.StringVar(root),
                },
            },
            "crop": {
                "crop_enabled": {
                    "default": True,
                    "var": tk.BooleanVar(root),
                },
                "width": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "height": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "original_width": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "original_height": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "left_top_x": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "left_top_y": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "original_left_top_x": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "original_left_top_y": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
            },
            "trim": {
                "trim_enabled": {
                    "default": True,
                    "var": tk.BooleanVar(root),
                },
                "hh_start": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "mm_start": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "ss_start": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "ms_start": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "hh_end": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "mm_end": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "ss_end": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "ms_end": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "original_hh_end": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "original_mm_end": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "original_ss_end": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
                "original_ms_end": {
                    "default": 0,
                    "var": tk.IntVar(root),
                },
            },
            "videofilters": {
                "selected": {
                    "default": "",
                    "var": tk.StringVar(root),
                },
            },
            "libx264": {
                "crf": {
                    "default": 23,
                    "var": tk.IntVar(root),
                },
                "preset": {
                    "default": "medium",
                    "var": tk.StringVar(root),
                },
                "tune": {
                    "default": "DEFAULT",
                    "var": tk.StringVar(root),
                },
            },
            "libx265": {
                "crf": {
                    "default": 28,
                    "var": tk.IntVar(root),
                },
                "preset": {
                    "default": "medium",
                    "var": tk.StringVar(root),
                },
                "tune": {
                    "default": "DEFAULT",
                    "var": tk.StringVar(root),
                },
            },
        }
        self.video_filter_args: list[tuple[filters.FiltersLiteral, dict[str, str]]] = []

    def reset_settings_to_default(self) -> None:
        for section in self.settings.values():
            for option in section.values():
                var = option.get("var")
                default = option.get("default")
                if var is not None and default is not None:
                    var.set(default)
        self.video_filter_args = []
