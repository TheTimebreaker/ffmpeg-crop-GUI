from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, Any, Final, Literal

from tkinterdnd2 import DND_FILES

from core import common, gui_vars, media_info

if TYPE_CHECKING:
    from main import GUI


class InOut(ttk.Frame):
    padx = 5
    pady = 5

    def __init__(
        self,
        master: ttk.Notebook | None = None,
        *,
        border: float | str | None = None,
        borderwidth: float | str | None = None,
        class_: Any = "",
        cursor: Any = "",
        height: int = 0,
        name: str | None = None,
        padding: (
            float
            | str
            | tuple[float | str]
            | tuple[float | str, float | str]
            | tuple[float | str, float | str, float | str]
            | tuple[float | str, float | str, float | str, float | str]
            | None
        ) = None,
        relief: Literal["raised", "sunken", "flat", "ridge", "solid", "groove"] | None = None,
        style: Any = "",
        takefocus: Any = "",
        width: int = 0,
        parent: GUI,
        root: tk.Tk,
        gui_vars: gui_vars.GuiVars,
    ) -> None:
        super().__init__(
            master,
            border=border,  # type:ignore
            borderwidth=borderwidth,  # type:ignore
            class_=class_,
            cursor=cursor,
            height=height,
            name=name,  # type:ignore
            padding=padding,  # type:ignore
            relief=relief,  # type:ignore
            style=style,
            takefocus=takefocus,
            width=width,
        )
        self.gui_vars = gui_vars
        self.parent = parent
        self.root = root
        self.CODECS_VIDEO: Final = (  # pylint:disable=C0103
            "libx264",
            "libx265",
        )

        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        self.file_source_label = ttk.Label(
            self,
            text="Source file",
        )
        self.file_source_label.grid(row=0, column=0, sticky="ew", padx=self.padx, pady=self.pady)

        self.downloadlocation_entry = ttk.Label(
            self,
            textvariable=self.gui_vars.settings["general"]["file"]["var"],
        )
        self.downloadlocation_entry.grid(row=0, column=1, sticky="ew", padx=self.padx, pady=self.pady)

        self.drop_target_register(DND_FILES)  # type:ignore
        self.dnd_bind(  # type:ignore
            "<<Drop>>",
            self.set_file_ondrop,
        )
        self.downloadlocation_entry.bind("<Double-Button-1>", self.set_file_dialogue)

        ttk.Separator(self, orient="horizontal").grid(row=6, column=0, columnspan=2, sticky="ew", padx=self.padx, pady=self.pady)

        ttk.Label(
            self,
            text="Additional settings",
        ).grid(row=7, column=0, sticky="ew", padx=self.padx, pady=self.pady)

        self.autonormalize_btn = ttk.Checkbutton(
            self,
            text="Automatically normalize audio to -1.0 dB",
            variable=self.gui_vars.settings["general"]["normalize_audio"]["var"],
        )
        self.autonormalize_btn.grid(row=7, column=1, sticky="ew", padx=self.padx, pady=self.pady)

        ttk.Separator(self, orient="horizontal").grid(row=8, column=0, columnspan=2, sticky="ew", padx=self.padx, pady=self.pady)
        video_encoder_label = ttk.Label(self, text="Video encoder\n(if needed)")
        video_encoder_label.grid(row=9, column=0, sticky="ew", padx=self.padx, pady=self.pady)
        common.ToolTip(
            video_encoder_label,
            "\n".join(
                [
                    "This tool will attempt to copy the video feed if possible and",
                    "only reencode the video with settings selected here if needed.",
                    "Settings that require reencoding include cropping and trimming.",
                ]
            ),
        )
        ttk.Checkbutton(self, text="Force reencoding", variable=self.gui_vars.settings["general"]["force_reencoding_video"]["var"]).grid(
            row=9, column=1, padx=self.padx, pady=self.pady, sticky="ew"
        )
        encoder = ttk.Combobox(
            self, textvariable=self.gui_vars.settings["general"]["selected_encoder_video"]["var"], values=self.CODECS_VIDEO, state="readonly"
        )
        encoder.grid(sticky="ew", row=10, column=1, padx=self.padx, pady=self.pady)
        encoder.bind("<<ComboboxSelected>>", self.update_codec_frames)

        self.codec_options_frame = ttk.Frame(self)
        self.codec_options_frame.grid(row=11, column=1, sticky="ew", padx=self.padx, pady=self.pady)
        self._init_codec_frames()
        self.update_codec_frames(None)

        self.grid_rowconfigure(12, weight=1)

    def _init_codec_frames(self) -> None:
        def _libx264() -> ttk.LabelFrame:
            f = ttk.LabelFrame(self.codec_options_frame, text="libx264 options")
            f.columnconfigure(0, weight=0)
            f.columnconfigure(1, weight=1)

            # CRF
            crf = ttk.Label(f, text="CRF")
            crf.grid(row=0, column=0, sticky="w", padx=self.padx, pady=self.pady)
            common.ToolTip(
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
            tk.Scale(
                f,
                from_=0,
                to=51,
                variable=self.gui_vars.settings["libx264"]["crf"]["var"],  # type:ignore
                showvalue=True,
                orient="horizontal",
            ).grid(row=0, column=1, sticky="ew", padx=self.padx, pady=self.pady)

            # Preset
            preset = ttk.Label(f, text="Preset")
            preset.grid(row=1, column=0, sticky="w", padx=self.padx, pady=self.pady)
            common.ToolTip(
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
                textvariable=self.gui_vars.settings["libx264"]["preset"]["var"],
                values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo"],
                state="readonly",
            ).grid(row=1, column=1, sticky="ew", padx=self.padx, pady=self.pady)

            # Tune
            tune = ttk.Label(f, text="Tune")
            tune.grid(row=2, column=0, sticky="w", padx=self.padx, pady=self.pady)
            common.ToolTip(
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
                textvariable=self.gui_vars.settings["libx264"]["tune"]["var"],
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
            common.ToolTip(
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
            tk.Scale(
                f,
                from_=0,
                to=51,
                variable=self.gui_vars.settings["libx265"]["crf"]["var"],  # type:ignore
                showvalue=True,
                orient="horizontal",
            ).grid(row=0, column=1, sticky="ew", padx=self.padx, pady=self.pady)

            # Preset
            preset = ttk.Label(f, text="Preset")
            preset.grid(row=1, column=0, sticky="w", padx=self.padx, pady=self.pady)
            common.ToolTip(
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
                textvariable=self.gui_vars.settings["libx265"]["preset"]["var"],
                values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow", "placebo"],
                state="readonly",
            ).grid(row=1, column=1, sticky="ew", padx=self.padx, pady=self.pady)

            # Tune
            tune = ttk.Label(f, text="Tune")
            tune.grid(row=2, column=0, sticky="w", padx=self.padx, pady=self.pady)
            common.ToolTip(
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
                textvariable=self.gui_vars.settings["libx265"]["tune"]["var"],
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
        selected_encoder = self.gui_vars.settings["general"]["selected_encoder_video"]["var"].get()
        self.codec_options_frames[selected_encoder].pack(expand=True, fill="both")

    def set_file_dialogue(self, _: Any) -> None:
        path = filedialog.askopenfilename()
        if path:
            self.set_file(path)

    def set_file_ondrop(self, event: Any) -> None:
        files = self.root.tk.splitlist(event.data)
        if files:
            self.set_file(files[0])

    def set_file(self, path: str) -> None:
        self.parent._reset_to_defaults()

        v = media_info.get_video_info(path)
        self.parent.max_volume = v.max_volume
        self.gui_vars.settings["general"]["file"]["var"].set(path)

        self.gui_vars.settings["crop"]["width"]["var"].set(v.width)
        self.gui_vars.settings["crop"]["height"]["var"].set(v.height)
        self.gui_vars.settings["crop"]["left_top_x"]["var"].set(0)
        self.gui_vars.settings["crop"]["left_top_y"]["var"].set(0)
        self.gui_vars.settings["crop"]["original_width"]["var"].set(v.width)
        self.gui_vars.settings["crop"]["original_height"]["var"].set(v.height)
        self.gui_vars.settings["crop"]["original_left_top_x"]["var"].set(0)
        self.gui_vars.settings["crop"]["original_left_top_y"]["var"].set(0)

        self.gui_vars.settings["trim"]["hh_start"]["var"].set(0)
        self.gui_vars.settings["trim"]["mm_start"]["var"].set(0)
        self.gui_vars.settings["trim"]["ss_start"]["var"].set(0)
        self.gui_vars.settings["trim"]["ms_start"]["var"].set(0)
        self.gui_vars.settings["trim"]["hh_end"]["var"].set(v.duration.hh)
        self.gui_vars.settings["trim"]["mm_end"]["var"].set(v.duration.mm)
        self.gui_vars.settings["trim"]["ss_end"]["var"].set(v.duration.ss)
        self.gui_vars.settings["trim"]["ms_end"]["var"].set(v.duration.ms)

        self.gui_vars.settings["trim"]["original_hh_end"]["var"].set(v.duration.hh)
        self.gui_vars.settings["trim"]["original_mm_end"]["var"].set(v.duration.mm)
        self.gui_vars.settings["trim"]["original_ss_end"]["var"].set(v.duration.ss)
        self.gui_vars.settings["trim"]["original_ms_end"]["var"].set(v.duration.ms)
