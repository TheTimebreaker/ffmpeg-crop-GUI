import datetime
import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, overload


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
