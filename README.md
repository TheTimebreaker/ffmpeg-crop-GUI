<h1>Welcome to FFmpeg Crop GUI</h1>
It's another GUI wrapper for one of the best open source projects ever!

<h2>Features</h2>
The main idea behind this project for me was that I often wanted to do simple stuff like cutting away the final few seconds of a video or cropping into the video to remove black borders from a video that doesn't need them. However, I also didn't want to memorize all the ffmpeg command line magic and debug it constantly just because I missed an apostrophe somewhere.

So I developed this program, which makes simple edits like that a matter of seconds instead of minutes.

Features include:

* Easy access to cropping and trimming
* Audio normalization
* Limited access to advanced filters like drawing text onto a video

<h2>Requirements</h2>

* `ffmpeg`: needs to be installed in such a way that you can run it anywhere from the console.
* `Python 3.14` and `PySide6` (installed automatically with the project dependencies)

<h2>Installation</h2>

* You can download pre-compiled, read-to-use executables for Windows in the [release tab](https://github.com/TheTimebreaker/duplicate_image_finder/releases)
    * <i>These still require ffmpeg to be installed on your system!</i>
* Compile it yourself
    * Download the repository (by using `git clone`)
    * Open the repository directory in your terminal (the repo directory is where the directory `/src` and the file `Makefile` are)
    * Install dependencies with uv: `uv sync --group build`
    * Run the application with `uv run python src/main.py`
    * Run either `make build` if you have make installed or `pyinstaller ffmpeg_crop_gui.spec`
    * The compiled executable should appear under `/dist`