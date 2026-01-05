import subprocess
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Any

from tkinterdnd2 import DND_FILES, TkinterDnD


class GUI:
    padx = 5
    pady = 5

    def __init__(self, root: TkinterDnD.Tk) -> None:
        self.root = root
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.title("YouTube manager")

        self.entry_width = 80
        self.label_width = 15

        # File path
        self.source_label = ttk.Label(
            self.root,
            text="Source file",
        )
        self.source_label.grid(row=0, column=0, sticky="w", padx=self.padx, pady=self.pady)

        self.source_file_txt_null = "Click the button on the right or Drag & drop file ..."
        self.source_file_var = tk.StringVar(self.root, value=self.source_file_txt_null)
        self.downloadlocation_entry = ttk.Label(
            self.root,
            textvariable=self.source_file_var,
            width=self.entry_width,
        )
        self.downloadlocation_entry.drop_target_register(DND_FILES)  # type:ignore
        self.downloadlocation_entry.dnd_bind(  # type:ignore
            "<<Drop>>",
            self.on_drop,
        )

        self.downloadlocation_entry.grid(row=0, column=1, sticky="ew", padx=self.padx, pady=self.pady)
        ttk.Button(
            self.root,
            text="Select Location",
            command=self.set_download_location,
        ).grid(row=0, column=2, sticky="ew", padx=self.padx, pady=self.pady)

        # Left top pixel
        ttk.Label(
            self.root,
            text="Top left corner (X / Y)",
        ).grid(row=1, column=0, sticky="w", padx=self.padx, pady=self.pady)
        self.left_top_x = tk.IntVar(self.root)
        self.left_top_y = tk.IntVar(self.root)
        ttk.Spinbox(
            self.root,
            textvariable=self.left_top_x,
            from_=0,
            to=5000,
        ).grid(row=1, column=1, sticky="w", padx=self.padx, pady=self.pady)
        ttk.Spinbox(
            self.root,
            textvariable=self.left_top_y,
            from_=0,
            to=5000,
        ).grid(row=1, column=2, sticky="w", padx=self.padx, pady=self.pady)

        # Box Dimensions
        ttk.Label(
            self.root,
            text="Box width (X / Y)",
        ).grid(row=2, column=0, sticky="w", padx=self.padx, pady=self.pady)
        self.width_x = tk.IntVar(self.root)
        self.width_y = tk.IntVar(self.root)
        ttk.Spinbox(
            self.root,
            textvariable=self.width_x,
            from_=0,
            to=5000,
        ).grid(row=2, column=1, sticky="w", padx=self.padx, pady=self.pady)
        ttk.Spinbox(
            self.root,
            textvariable=self.width_y,
            from_=0,
            to=5000,
        ).grid(row=2, column=2, sticky="w", padx=self.padx, pady=self.pady)

        ttk.Separator(self.root, orient="horizontal").grid(row=3, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)

        self.process_button = ttk.Button(
            self.root,
            text="Process",
            command=self.process,
        )
        self.process_button.grid(row=4, column=0, columnspan=3, sticky="ew", padx=self.padx, pady=self.pady)

    def set_download_location(self) -> None:
        path = filedialog.askopenfilename()
        if path:
            self.source_file_var.set(path)

    def on_drop(self, event: Any) -> None:
        files = self.root.tk.splitlist(event.data)
        if files:
            self.source_file_var.set(files[0])

    def process(self) -> None:
        cmd = [
            "ffmpeg",
            "-i",
            self.source_file_var.get(),
            "-vf",
            f"crop={self.width_x.get()}:{self.width_y.get()}:{self.left_top_x.get()}:{self.left_top_y.get()}",
            ".".join(self.source_file_var.get().split(".")[0:-1]) + "-cropped." + self.source_file_var.get().split(".")[-1],
        ]
        subprocess.run(cmd, shell=True)
        self.source_file_var.set(self.source_file_txt_null)
        self.width_x.set(0)
        self.width_y.set(0)
        self.left_top_x.set(0)
        self.left_top_y.set(0)

    def on_close(self) -> None:
        self.root.destroy()


def main() -> None:
    root = TkinterDnD.Tk()
    GUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
