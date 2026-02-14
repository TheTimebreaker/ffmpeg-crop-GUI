from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any

import common
import gui_vars

if TYPE_CHECKING:
    from main import GUI


class CropTrim(ttk.Frame):
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

        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        crop_enabled = ttk.Checkbutton(self, variable=self.gui_vars.settings["crop"]["crop_enabled"]["var"], text="Enable Crop")
        crop_enabled.grid(row=0, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)
        common.ToolTip(
            crop_enabled,
            text="Allows the encoder to CROP the video with the settings specified here."
            "\nThe system is smart and will only actually crop if these values were changed from the original values.",
        )

        # Left top pixel
        ttk.Label(
            self,
            text="Top left corner (X / Y)",
        ).grid(row=2, column=0, sticky="w", padx=self.padx, pady=self.pady)
        ttk.Spinbox(
            self,
            textvariable=self.gui_vars.settings["crop"]["left_top_x"]["var"],
            from_=0,
            to=50000,
        ).grid(row=2, column=1, sticky="ew", padx=self.padx, pady=self.pady)
        ttk.Spinbox(
            self,
            textvariable=self.gui_vars.settings["crop"]["left_top_y"]["var"],
            from_=0,
            to=50000,
        ).grid(row=2, column=2, sticky="ew", padx=self.padx, pady=self.pady)

        # Box Dimensions
        ttk.Label(
            self,
            text="Box width (X / Y)",
        ).grid(row=3, column=0, sticky="w", padx=self.padx, pady=self.pady)
        ttk.Spinbox(
            self,
            textvariable=self.gui_vars.settings["crop"]["width"]["var"],
            from_=0,
            to=50000,
        ).grid(row=3, column=1, sticky="ew", padx=self.padx, pady=self.pady)
        ttk.Spinbox(
            self,
            textvariable=self.gui_vars.settings["crop"]["height"]["var"],
            from_=0,
            to=50000,
        ).grid(row=3, column=2, sticky="ew", padx=self.padx, pady=self.pady)

        ttk.Separator(self, orient="horizontal").grid(row=4, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)

        # Trim
        trim_enabled = ttk.Checkbutton(self, variable=self.gui_vars.settings["trim"]["trim_enabled"]["var"], text="Enable Trim")
        trim_enabled.grid(row=5, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)
        common.ToolTip(
            trim_enabled,
            text="Allows the encoder to TRIM the video with the settings specified here."
            "\nThe system is smart and will only actually crop if these values were changed from the original values.",
        )

        ttk.Label(
            self,
            text="Timestamp Start (HH:MM:SS.MS)",
        ).grid(row=6, column=0, sticky="w", padx=self.padx, pady=self.pady)
        timestamp_start_frame = ttk.Frame(self)
        timestamp_start_frame.grid(row=6, column=1, columnspan=2, sticky="ew", padx=self.padx, pady=self.pady)
        ttk.Spinbox(
            timestamp_start_frame, textvariable=self.gui_vars.settings["trim"]["hh_start"]["var"], from_=0, to=99, width=3, format="%02.0f"
        ).pack(side="left", fill="x", expand=True)
        ttk.Label(timestamp_start_frame, text=" : ").pack(side="left")
        ttk.Spinbox(
            timestamp_start_frame, textvariable=self.gui_vars.settings["trim"]["mm_start"]["var"], from_=0, to=59, width=3, format="%02.0f"
        ).pack(side="left", fill="x", expand=True)
        ttk.Label(timestamp_start_frame, text=" : ").pack(side="left")
        ttk.Spinbox(
            timestamp_start_frame, textvariable=self.gui_vars.settings["trim"]["ss_start"]["var"], from_=0, to=59, width=3, format="%02.0f"
        ).pack(side="left", fill="x", expand=True)
        ttk.Label(timestamp_start_frame, text=" . ").pack(side="left")
        ttk.Spinbox(timestamp_start_frame, textvariable=self.gui_vars.settings["trim"]["ms_start"]["var"], from_=0, to=999, width=4).pack(
            side="left", fill="x", expand=True
        )

        # Timestamp End
        ttk.Label(
            self,
            text="Timestamp End (HH:MM:SS.MS)",
        ).grid(row=7, column=0, sticky="w", padx=self.padx, pady=self.pady)
        timestamp_end_frame = ttk.Frame(self)
        timestamp_end_frame.grid(row=7, column=1, columnspan=2, sticky="ew", padx=self.padx, pady=self.pady)
        ttk.Spinbox(timestamp_end_frame, textvariable=self.gui_vars.settings["trim"]["hh_end"]["var"], from_=0, to=99, width=3, format="%02.0f").pack(
            side="left", fill="x", expand=True
        )
        ttk.Label(timestamp_end_frame, text=" : ").pack(side="left")
        ttk.Spinbox(timestamp_end_frame, textvariable=self.gui_vars.settings["trim"]["mm_end"]["var"], from_=0, to=59, width=3, format="%02.0f").pack(
            side="left", fill="x", expand=True
        )
        ttk.Label(timestamp_end_frame, text=" : ").pack(side="left")
        ttk.Spinbox(timestamp_end_frame, textvariable=self.gui_vars.settings["trim"]["ss_end"]["var"], from_=0, to=59, width=3, format="%02.0f").pack(
            side="left", fill="x", expand=True
        )
        ttk.Label(timestamp_end_frame, text=" . ").pack(side="left")
        ttk.Spinbox(timestamp_end_frame, textvariable=self.gui_vars.settings["trim"]["ms_end"]["var"], from_=0, to=999, width=4).pack(
            side="left", fill="x", expand=True
        )
