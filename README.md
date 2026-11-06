# SnagForge

**Capture. Annotate. Explain.**

An independent, GPL-3.0-licensed screenshot and recording workbench built for Ubuntu desktops. Inspired by common screen capture workflows; not affiliated with TechSmith and not compatible with Snagit project files.

**Version 0.1.0-alpha · Target: Ubuntu 26.x GNOME / Wayland · Python 3.10+**

> This is an early source release, not full Snagit feature parity. Editor, stitching, selection mapping and portal protocol behavior have automated tests. Live capture, audio and encoding still require validation on a real Ubuntu 26 desktop. There are no fabricated recording screenshots or claimed live recording results.

![Actual SnagForge editor, rendered with synthetic demonstration data](docs/screenshots/01-editor.png)

## Install on Ubuntu

Keep the extracted project in a permanent directory before installing; the launcher refers to that directory.

```bash
chmod +x install.sh run.sh publish.sh
./install.sh --system-deps
./run.sh
```

The first command installs Ubuntu packages with `sudo`, creates a project-local virtual environment, downloads Python dependencies from PyPI and adds an application menu entry. Run it as your normal desktop user. If dependencies are already installed, use `./install.sh`.

Install dependencies only on the Ubuntu computer where you want to run the app. Do not run the GUI as root. No Docker, web server or account is needed to use it.

## Features in this source release

| Capability | Status / behavior |
|---|---|
| Screenshots | Desktop portal picker, then full source or drag a region on the captured preview |
| Screen/window recording | MP4, H.264 video, 30 fps, desktop portal + PipeWire + GStreamer; desktop validation pending |
| Region video | Select a rectangle on a still preview of the chosen screen/window; cropped before encoding |
| Audio | Choose microphone/default input OR default system output; AAC in MP4, MP3 audio-only |
| Scrolling capture | Guided captures/imports, fixed manual overlap, optional header/footer trim; vertical only |
| Annotation | Arrow, line, pen, rectangle, ellipse, text, numbered steps, highlight |
| Image editing | Crop, resize preserving aspect ratio, rotate, pixelate, opaque redact, spotlight |
| History | Undo/redo up to 20 raster snapshots in memory |
| Export | Flattened PNG, JPEG, WebP; image clipboard copy and paste |
| OCR | Local Tesseract text extraction, review/copy; no in-place text editing |
| Recent exports | Last 80 image/audio/video exports in `~/Pictures/SnagForge`, newest first |
| Delay | 0–30 seconds before opening the capture flow |
| Help | Illustrated manual in Markdown and offline HTML, opened from the app |

![Actual region-selection dialog](docs/screenshots/02-region-selection.png)

## Record video or audio

1. Choose **MP4 video** or **MP3 audio**.
2. Choose **None**, **Microphone**, or **System audio**. MP3 requires an audio source.
3. For video, enable **Select region** if you want a crop.
4. Click **Record**, choose a file and approve the desktop screen/window picker.
5. If selecting a region, drag a rectangle on the source preview or choose **Full source**.
6. The app minimizes while recording. Restore it from the desktop and press **Stop & save**. Wait for the file to finalize.

There is currently no webcam, pause/resume, tray stop control or simultaneous microphone/system mixing. Restoring the app can appear in a full-monitor recording. Record a separate window to avoid that, or trim externally afterward. Audio-only uses the selected/default source without a screen picker.

![Actual recording controls in the idle setup state](docs/screenshots/04-recording-setup.png)

## Scrolling capture

Use **Scrolling capture → Capture section**, scroll manually, and repeat. Select the same width/area and scroll by a constant distance. Set **Overlap (px)** to the duplicated vertical pixel count after header/footer trim. Choose **Stitch into editor**, inspect every seam, then export. Importing pre-captured sections also works.

This release does not automatically scroll, detect overlap or remove repeated sticky headers. Full instructions and worked pixel examples are in the [manual](docs/MANUAL.md).

![Actual guided scrolling capture dialog](docs/screenshots/03-scrolling-capture.png)

## Documentation

- [Illustrated user manual](docs/MANUAL.md) · [Offline HTML manual](docs/MANUAL.html)
- [Feature comparison and roadmap](docs/FEATURES.md)
- [Validation and desktop acceptance checklist](docs/VALIDATION.md)
- [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [GPL-3.0 license](LICENSE)

## Development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen .venv/bin/python docs/render_screenshots.py
.venv/bin/python app.py
```

Application modules: `app.py` (UI), `editor.py` (raster editor), `portal.py` (D-Bus desktop requests), `workers.py` (capture/recording lifecycle), `media.py` (pipelines/stitching). Tests use synthetic images and a fake D-Bus transport; they do not record the developer's desktop.

Capture uses the system [Screenshot](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Screenshot.html) and [ScreenCast](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html) portals. Media encoding uses [GStreamer](https://gstreamer.freedesktop.org/documentation/tools/gst-launch.html). UI rendering uses [Qt for Python](https://doc.qt.io/qtforpython-6/). The app executes local capture/encoder processes, not shell-interpolated media commands. Capture workers use separate threads.

## Source repository

The public project is [skarasulu19/SnagForge](https://github.com/skarasulu19/SnagForge).

```bash
git clone https://github.com/skarasulu19/SnagForge.git
cd SnagForge
chmod +x install.sh run.sh publish.sh
./install.sh --system-deps
./run.sh
```

The repository contains the application, illustrated manual, screenshots, tests and feature roadmap. It is an alpha source release; live Ubuntu 26 capture validation is pending.

## Licensing

This repository uses GPL-3.0, as selected when the repository was created. The original alpha's MIT copyright and permission notice is retained in LICENSE-MIT. Dependencies retain their own licenses: PySide6/Qt include LGPL/GPL/commercial terms, dbus-next is MIT, Pillow has its own permissive license, and GStreamer components/codecs have their own terms. This is source distribution; review dependency and codec obligations before redistributing a bundled binary. Snagit names are used only for comparison, without copied branding or assets.
