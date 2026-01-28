import datetime
import json
import logging
import re
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Any, Literal, overload

from tkinterdnd2 import DND_FILES, TkinterDnD


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


class GUI:
    padx = 5
    pady = 5

    def __init__(self, root: TkinterDnD.Tk) -> None:
        self.root = root
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.title("FFmpeg Crop GUI")
        self.root.minsize(800, 0)
        self.root.resizable(True, False)

        self.label_width = 15
        self.max_volume: float = 0.0

        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.columnconfigure(2, weight=1)

        # File path
        self.source_label = ttk.Label(
            self.root,
            text="Source file",
        )
        self.source_label.grid(row=0, column=0, sticky="ew", padx=self.padx, pady=self.pady)

        self.source_file_txt_null = "Double click here or Drag & drop file ..."
        self.source_file_var = tk.StringVar(self.root, value=self.source_file_txt_null)
        self.downloadlocation_entry = ttk.Label(
            self.root,
            textvariable=self.source_file_var,
        )
        self.downloadlocation_entry.drop_target_register(DND_FILES)  # type:ignore
        self.downloadlocation_entry.dnd_bind(  # type:ignore
            "<<Drop>>",
            self.set_file_ondrop,
        )
        self.downloadlocation_entry.bind("<Double-Button-1>", self.set_file_dialogue)
        self.downloadlocation_entry.grid(row=0, column=1, sticky="ew", padx=self.padx, pady=self.pady, columnspan=2)

        ttk.Separator(self.root, orient="horizontal").grid(row=1, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)

        # Left top pixel
        ttk.Label(
            self.root,
            text="Top left corner (X / Y)",
        ).grid(row=2, column=0, sticky="w", padx=self.padx, pady=self.pady)
        self.left_top_x = tk.IntVar(self.root)
        self.left_top_y = tk.IntVar(self.root)
        ttk.Spinbox(
            self.root,
            textvariable=self.left_top_x,
            from_=0,
            to=5000,
        ).grid(row=2, column=1, sticky="ew", padx=self.padx, pady=self.pady)
        ttk.Spinbox(
            self.root,
            textvariable=self.left_top_y,
            from_=0,
            to=5000,
        ).grid(row=2, column=2, sticky="ew", padx=self.padx, pady=self.pady)

        # Box Dimensions
        ttk.Label(
            self.root,
            text="Box width (X / Y)",
        ).grid(row=3, column=0, sticky="w", padx=self.padx, pady=self.pady)
        self.width_x = tk.IntVar(self.root)
        self.height_y = tk.IntVar(self.root)
        ttk.Spinbox(
            self.root,
            textvariable=self.width_x,
            from_=0,
            to=5000,
        ).grid(row=3, column=1, sticky="ew", padx=self.padx, pady=self.pady)
        ttk.Spinbox(
            self.root,
            textvariable=self.height_y,
            from_=0,
            to=5000,
        ).grid(row=3, column=2, sticky="ew", padx=self.padx, pady=self.pady)

        ttk.Separator(self.root, orient="horizontal").grid(row=4, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)
        ttk.Label(
            self.root,
            text="Timestamps Start / End (HH:MM:SS.MS)",
        ).grid(row=5, column=0, sticky="ew", padx=self.padx, pady=self.pady)

        self.timestamp_frame = ttk.Frame(self.root)
        self.timestamp_frame.grid(row=5, column=1, sticky="ew", padx=self.padx, pady=self.pady, columnspan=2)
        self.hh_start = ttk.Spinbox(self.timestamp_frame, from_=0, to=99, width=3, format="%02.0f")
        self.hh_start.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_frame, text=" : ").pack(side="left")
        self.mm_start = ttk.Spinbox(self.timestamp_frame, from_=0, to=59, width=3, format="%02.0f")
        self.mm_start.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_frame, text=" : ").pack(side="left")
        self.ss_start = ttk.Spinbox(self.timestamp_frame, from_=0, to=59, width=3, format="%02.0f")
        self.ss_start.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_frame, text=" . ").pack(side="left")
        self.ms_start = ttk.Spinbox(self.timestamp_frame, from_=0, to=999, width=4)
        self.ms_start.pack(side="left", fill="x", expand=True)
        ttk.Separator(self.timestamp_frame, orient="vertical").pack(side="left", expand=True, fill="y")

        self.hh_end = ttk.Spinbox(self.timestamp_frame, from_=0, to=99, width=3, format="%02.0f")
        self.hh_end.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_frame, text=" : ").pack(side="left")
        self.mm_end = ttk.Spinbox(self.timestamp_frame, from_=0, to=59, width=3, format="%02.0f")
        self.mm_end.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_frame, text=" : ").pack(side="left")
        self.ss_end = ttk.Spinbox(self.timestamp_frame, from_=0, to=59, width=3, format="%02.0f")
        self.ss_end.pack(side="left", fill="x", expand=True)
        ttk.Label(self.timestamp_frame, text=" . ").pack(side="left")
        self.ms_end = ttk.Spinbox(self.timestamp_frame, from_=0, to=999, width=4)
        self.ms_end.pack(side="left", fill="x", expand=True)

        ttk.Separator(self.root, orient="horizontal").grid(row=6, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)

        ttk.Label(
            self.root,
            text="Additional settings",
        ).grid(row=7, column=0, sticky="ew", padx=self.padx, pady=self.pady)

        self.autonormalize_var = tk.BooleanVar(self.root, True)
        self.autonormalize_btn = ttk.Checkbutton(
            self.root,
            text="Automatically normalize audio to -1.0 dB",
            variable=self.autonormalize_var,
        )
        self.autonormalize_btn.grid(row=7, column=1, columnspan=2, sticky="ew", padx=self.padx, pady=self.pady)

        ttk.Separator(self.root, orient="horizontal").grid(row=8, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)
        self.process_button = ttk.Button(
            self.root,
            text="Process",
            command=self.process,
        )
        self.process_button.grid(row=9, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)

    def set_file_dialogue(self, _: Any) -> None:
        path = filedialog.askopenfilename()
        if path:
            self.set_file(path)

    def set_file_ondrop(self, event: Any) -> None:
        files = self.root.tk.splitlist(event.data)
        if files:
            self.set_file(files[0])

    def set_file(self, path: str) -> None:
        v = get_video_info(path)
        self.max_volume = v.max_volume
        self.source_file_var.set(path)

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

    def process(self) -> None:
        timestamps = self.get_timestamps()
        if timestamps is False:
            return
        timestamp_start, timestamp_end = timestamps

        crops = self.get_crop()
        if crops is False:
            return
        width, height, left_top_x, left_top_y = crops

        video_copy = True
        audio_copy = True
        cmd = [
            "ffmpeg",
            "-i",
            self.source_file_var.get(),
            "-y",  # overwrite always
        ]

        # timestamp command
        if timestamp_start and timestamp_start != self.original_start:
            cmd.append("-ss")
            cmd.append(str(timestamp_start))
            video_copy = False
        if timestamp_end and timestamp_end != self.original_end:
            cmd.append("-to")
            cmd.append(str(timestamp_end))
            video_copy = False

        # crop command
        if (
            width != self.original_width
            or height != self.original_height
            or left_top_x != self.original_left_top_x
            or left_top_y != self.original_left_top_y
        ):
            cmd.append("-filter:v")
            cmd.append(f"crop={width}:{height}:{left_top_x}:{left_top_y}")
            video_copy = False

        # normalization
        if self.autonormalize_var.get():
            cmd.append("-filter:a")
            cmd.append(f"volume={-1 * self.max_volume - 1}dB")
            audio_copy = False

        # COPYING CODECS
        if video_copy:
            cmd.append("-c:v")
            cmd.append("copy")
        if audio_copy:
            cmd.append("-c:a")
            cmd.append("copy")

        # output filename
        cmd.append(".".join(self.source_file_var.get().split(".")[0:-1]) + "-cropped." + self.source_file_var.get().split(".")[-1])

        print(" ".join(cmd))
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
