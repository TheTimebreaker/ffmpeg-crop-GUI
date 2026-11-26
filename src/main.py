import atexit
import shlex
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Literal, override

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from send2trash import send2trash  # type: ignore[import-untyped]

from core import gui_vars, media_info
from tabs import croptrim, inout, videofilter

# TODO: dont reset encoder settings
# TODO: add reset encoder settings button
# TODO: audio encoder
# TODO: progress bar


def printable_command(cmd: list[str]) -> str:
    if sys.platform == "win32":
        return subprocess.list2cmdline(cmd)
    return shlex.join(cmd)


def ffmpeg_drawtext_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("%", "%%").replace("'", "\\'")


class GUI(QMainWindow):
    def __init__(self, state: gui_vars.GuiVars) -> None:
        super().__init__()
        self.setWindowTitle("FFmpeg Crop GUI")
        self.setMinimumSize(800, 480)
        self.resize(920, 600)
        self.setAcceptDrops(True)
        self.cleanup_files: list[Path] = []
        self.gui_vars = state
        self.max_volume = 0.0
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        self.notebook = QTabWidget()
        self.inout = inout.InOut(self, self.gui_vars)
        self.tab_crop = croptrim.CropTrim(self, self.gui_vars)
        self.tab_videofilter = videofilter.Videofilter(self, self.gui_vars)
        self.notebook.addTab(self.inout, "Input / Output")
        self.notebook.addTab(self.tab_crop, "Crop / Trim")
        self.notebook.addTab(self.tab_videofilter, "Video Filters")
        layout.addWidget(self.notebook, 1)

        self.process_button = QPushButton("Process")
        self.process_button.clicked.connect(self.process)
        layout.addWidget(self.process_button)
        self.setCentralWidget(central)

    def _reset_to_defaults(self) -> None:
        self.gui_vars.reset_settings_to_default()
        self.sync_controls()

    def sync_controls(self) -> None:
        self.inout.sync_controls()
        self.tab_crop.sync_controls()
        self.tab_videofilter.update_videofilter_preview()

    @override
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._dropped_file(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    @override
    def dropEvent(self, event: QDropEvent) -> None:
        path = self._dropped_file(event.mimeData())
        if path:
            self.inout.set_file(path)
            event.acceptProposedAction()
        else:
            event.ignore()

    @staticmethod
    def _dropped_file(mime_data: QMimeData) -> str | None:
        if not mime_data.hasUrls():
            return None
        for url in mime_data.urls():
            if url.isLocalFile():
                return url.toLocalFile()
        return None

    def get_timestamps(self) -> tuple[media_info.Timestamp, media_info.Timestamp] | Literal[False]:
        try:
            values = self.gui_vars.settings["trim"]
            start = media_info.Timestamp(
                int(values["hh_start"]["var"].get()),
                int(values["mm_start"]["var"].get()),
                int(values["ss_start"]["var"].get()),
                int(values["ms_start"]["var"].get()),
            )
            end = media_info.Timestamp(
                int(values["hh_end"]["var"].get()),
                int(values["mm_end"]["var"].get()),
                int(values["ss_end"]["var"].get()),
                int(values["ms_end"]["var"].get()),
            )
        except TypeError, ValueError:
            QMessageBox.critical(self, "Invalid timestamps", "Timestamp values must be valid numbers.")
            return False
        return start, end

    def get_crop(self) -> tuple[int, int, int, int]:
        values = self.gui_vars.settings["crop"]
        return (
            int(values["width"]["var"].get()),
            int(values["height"]["var"].get()),
            int(values["left_top_x"]["var"].get()),
            int(values["left_top_y"]["var"].get()),
        )

    def get_encoder_args_video_libx264(self) -> list[str]:
        args = ["-c:v", "libx264"]
        settings = self.gui_vars.settings["libx264"]
        crf = settings["crf"]["var"].get()
        if crf != settings["crf"]["default"]:
            args.extend(["-crf", str(crf)])
        for option in ("preset", "tune"):
            selection = settings[option]["var"].get()
            if selection != settings[option]["default"]:
                args.extend([f"-{option}", str(selection)])
        return args

    def get_encoder_args_video_libx265(self) -> list[str]:
        args = ["-c:v", "libx265"]
        settings = self.gui_vars.settings["libx265"]
        crf = settings["crf"]["var"].get()
        if crf != settings["crf"]["default"]:
            args.extend(["-crf", str(crf)])
        for option in ("preset", "tune"):
            selection = settings[option]["var"].get()
            if selection != settings[option]["default"]:
                args.extend([f"-{option}", str(selection)])
        return args

    def get_encoder_args_video(self) -> list[str]:
        selected_encoder = self.gui_vars.settings["general"]["selected_encoder_video"]["var"].get()
        if selected_encoder == "libx264":
            return self.get_encoder_args_video_libx264()
        if selected_encoder == "libx265":
            return self.get_encoder_args_video_libx265()
        raise NotImplementedError(f"Encoder {selected_encoder} is not implemented.")

    def get_video_filter_args(self) -> list[str]:
        entry_strs: list[str] = []
        for filter_name, individual_call in self.gui_vars.video_filter_args:
            entry_args: list[str] = []
            for arg_name, arg_val in individual_call.items():
                if filter_name == "drawtext" and arg_name == "text":
                    path = Path(f"text_{uuid.uuid4()}.tmp.txt").resolve()
                    self.cleanup_files.append(path)
                    path.write_text(arg_val.replace("\\n", "\n"), encoding="utf-8", newline="\n")
                    entry_args.append(f"textfile='{ffmpeg_drawtext_escape(str(path))}'")
                else:
                    entry_args.append(f"{arg_name}='{ffmpeg_drawtext_escape(arg_val)}'")
            entry_strs.append(f"{filter_name}={':'.join(entry_args)}")
        return entry_strs

    def process(self) -> None:
        file = str(self.gui_vars.settings["general"]["file"]["var"].get())
        if not file:
            QMessageBox.critical(self, "No file selected", "You haven't selected a file to convert.")
            return

        timestamps = self.get_timestamps()
        if timestamps is False:
            return
        timestamp_start, timestamp_end = timestamps
        width, height, left_top_x, left_top_y = self.get_crop()

        video_copy = not self.gui_vars.settings["general"]["force_reencoding_video"]["var"].get()
        audio_copy = True
        cmd = ["ffmpeg", "-i", file, "-y"]

        if self.gui_vars.settings["trim"]["trim_enabled"]["var"].get():
            if timestamp_start != media_info.Timestamp(0, 0, 0, 0):
                cmd.extend(["-ss", str(timestamp_start)])
                video_copy = False
            original_end = media_info.Timestamp(
                self.gui_vars.settings["trim"]["original_hh_end"]["var"].get(),
                self.gui_vars.settings["trim"]["original_mm_end"]["var"].get(),
                self.gui_vars.settings["trim"]["original_ss_end"]["var"].get(),
                self.gui_vars.settings["trim"]["original_ms_end"]["var"].get(),
            )
            if timestamp_end != original_end:
                cmd.extend(["-to", str(timestamp_end)])
                video_copy = False

        video_filters: list[str] = []
        crop = self.gui_vars.settings["crop"]
        if self.gui_vars.settings["crop"]["crop_enabled"]["var"].get() and (
            width != crop["original_width"]["var"].get()
            or height != crop["original_height"]["var"].get()
            or left_top_x != crop["original_left_top_x"]["var"].get()
            or left_top_y != crop["original_left_top_y"]["var"].get()
        ):
            video_filters.append(f"crop={width}:{height}:{left_top_x}:{left_top_y}")
            video_copy = False
        if self.gui_vars.video_filter_args:
            video_filters.extend(self.get_video_filter_args())
            video_copy = False
        if video_filters:
            cmd.extend(["-filter:v", ",".join(video_filters)])

        if self.gui_vars.settings["general"]["normalize_audio"]["var"].get():
            cmd.extend(["-filter:a", f"volume={-1 * self.max_volume - 1}dB"])
            audio_copy = False

        cmd.extend(self.get_encoder_args_video() if not video_copy else ["-c:v", "copy"])
        if audio_copy:
            cmd.extend(["-c:a", "copy"])
        output_file = ".".join(file.split(".")[:-1]) + "-cropped." + file.split(".")[-1]
        cmd.append(output_file)

        print(cmd, printable_command(cmd))
        try:
            if sys.platform == "win32":
                result = subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW, check=False)
            else:
                result = subprocess.run(cmd, check=False)
        except OSError as error:
            QMessageBox.critical(self, "FFmpeg could not start", str(error))
            return
        if result.returncode:
            QMessageBox.critical(self, "FFmpeg failed", f"FFmpeg exited with code {result.returncode}.")
        else:
            QMessageBox.information(self, "Processing complete", f"Output saved to:\n{output_file}")


def cleanup(gui: GUI) -> None:
    for path in gui.cleanup_files:
        try:
            send2trash(path)
        except OSError as error:
            print(f"Could not remove temporary file {path}: {error}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FFmpeg Crop GUI")
    state = gui_vars.GuiVars()
    gui = GUI(state)
    atexit.register(cleanup, gui)
    gui.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
