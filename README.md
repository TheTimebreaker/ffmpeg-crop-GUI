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
* `Python 3.14` with `tkinter` working (the latter should be the default on Windows, but Linux may be a bit more work)

<h2>Installation</h2>

* You can download pre-compiled, read-to-use executables for Windows in the [release tab](https://github.com/TheTimebreaker/duplicate_image_finder/releases)
    * <i>These still require ffmpeg to be installed on your system!</i>
* Compile it yourself
    * Download the repository (either by using `git clone` or by downloading the ZIP straight from github)
    * Open the repository directory in your terminal (the repo directory is where the directory `/src` and the file `Makefile` are)
    * Create a virtual environment with Python 3.14 by running any of the following (verify first that calling python in the way youre doing it actually is using python 3.14):
        * `python3.14 -m venv .venv`
        * `python -m venv .venv`
        * `py -m venv .venv`
    * Activate the virtual environment
        * Windows: `.venv\Scripts\activate`
        * Linux: depends on console, usually some variation of `source .venv\bin\activate`
        * MacOS: idk, probably similar to Linux though
    * Install requirements: `pip install . && pip install pyinstaller`
        * <i>These are the requirements of the program and NOT the development requirements. For developing, run `pip install -r requirements.txt`</i>
    * Run either `make build` if you have make installed or `pyinstaller ffmpeg_crop_gui.spec`
    * The compiled executable should appear under `/dist`