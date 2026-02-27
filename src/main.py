import atexit
import shlex
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Literal

from send2trash import send2trash
from tkinterdnd2 import TkinterDnD

from core import gui_vars, media_info
from tabs import croptrim, inout, videofilter

# TODO: dont reset encoder settings
# TODO: add reset encoder settings button
# TODO: audio encoder
# TODO: progress bar


def printable_command(cmd: list[str]) -> str:
    if sys.platform == "win32":
        return subprocess.list2cmdline(cmd)
    else:
        return shlex.join(cmd)


def ffmpeg_drawtext_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("%", "%%").replace("'", "\\'")


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
        self.max_volume: float = 0.0

        self._build_ui()

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.inout = inout.InOut(self.notebook, parent=self, root=self.root, gui_vars=self.gui_vars)
        self.notebook.add(self.inout, text="Input / Output")

        self.tab_crop = croptrim.CropTrim(self.notebook, parent=self, root=self.root, gui_vars=self.gui_vars)
        self.notebook.add(self.tab_crop, text="Crop / Trim")

        self.tab_videofilter = videofilter.Videofilter(self.notebook, parent=self, root=self.root, gui_vars=self.gui_vars)
        self.notebook.add(self.tab_videofilter, text="Video Filters")

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", expand=True, padx=self.padx, pady=self.pady)
        self.process_button = ttk.Button(
            self.root,
            text="Process",
            command=self.process,
        )
        self.process_button.pack(fill="x", expand=True, padx=self.padx, pady=self.pady)

    def _reset_to_defaults(self) -> None:
        self.gui_vars.reset_settings_to_default()
        self.inout.update_codec_frames()
        self.tab_videofilter.update_videofilter_preview()

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
        crf_default: int = int(self.gui_vars.settings["libx264"]["crf"]["default"])
        crf_selection: int = self.gui_vars.settings["libx264"]["crf"]["var"].get()
        if crf_default != crf_selection:
            args.append("-crf")
            args.append(str(crf_selection))

        # preset
        preset_default: str = str(self.gui_vars.settings["libx264"]["preset"]["default"])
        preset_selection: str = self.gui_vars.settings["libx264"]["preset"]["var"].get()
        if preset_default != preset_selection:
            args.append("-preset")
            args.append(preset_selection)

        # tune
        tune_default: str = str(self.gui_vars.settings["libx264"]["tune"]["default"])
        tune_selection: str = self.gui_vars.settings["libx264"]["tune"]["var"].get()
        if tune_default != tune_selection:
            args.append("-tune")
            args.append(tune_selection)

        return args

    def get_encoder_args_video_libx265(self) -> list[str]:
        args: list[str] = ["-c:v", "libx265"]

        # crf
        crf_default: int = int(self.gui_vars.settings["libx265"]["crf"]["default"])
        crf_selection: int = self.gui_vars.settings["libx265"]["crf"]["var"].get()
        if crf_default != crf_selection:
            args.append("-crf")
            args.append(str(crf_selection))

        # preset
        preset_default: str = str(self.gui_vars.settings["libx265"]["preset"]["default"])
        preset_selection: str = self.gui_vars.settings["libx265"]["preset"]["var"].get()
        if preset_default != preset_selection:
            args.append("-preset")
            args.append(preset_selection)

        # tune
        tune_default: str = str(self.gui_vars.settings["libx265"]["tune"]["default"])
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
        for filter, individual_call in self.gui_vars.video_filter_args:
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
        if self.gui_vars.video_filter_args:
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
            subprocess.run(cmd)

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
