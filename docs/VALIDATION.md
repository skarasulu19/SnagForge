# Validation record

## Executed in the development environment

- Python 3.12 and PySide6 6.12; Linux headless Qt offscreen platform.
- Sixteen passing automated tests cover image annotation/crop/history/blur, editor and full-screen marquee coordinate mapping, marquee keyboard actions, opaque redaction, stitch pixel continuity, invalid stitch input, pipeline/audio/crop arguments, early portal responses, portal cancellation, idempotent portal cleanup, image bridge validation, bridge echo suppression and navigation confinement.
- Rendered and visually inspected actual editor/selection/scrolling/recording-setup widgets with synthetic sample data.
- Python compilation and shell syntax checks.

## Not verified here

There is no GNOME/Wayland desktop capture session in the development runtime. GStreamer could not be installed here because system package installation lacks privileges. Live portal capture, PipeWire negotiation, GStreamer encoding and sound routing have not been exercised end to end. Pipeline argument tests are not evidence of successfully encoded media. Ubuntu 26 compatibility is a target until the following checks pass.

## Acceptance checklist on Ubuntu 26

- [ ] Install into a permanent folder as a normal user; launch from Applications.
- [ ] Capture a screen, window and rectangular image selection; cancel every picker safely.
- [ ] Verify the full-screen marquee, live source-pixel dimensions, Enter for full source, Esc/right-click cancellation and reverse-direction drags.
- [ ] Verify coordinate mapping at 100%, 125%, 150% and 200% scaling on one and multiple monitors.
- [ ] Check delayed screenshot with a menu open.
- [ ] Annotate, crop, undo, redo, copy/paste and export PNG/JPEG/WebP; inspect pixels and dimensions.
- [ ] Stitch a page in three sections with known constant overlap and sticky header/footer trim; inspect seams.
- [ ] Record full screen and a separate window for 30 seconds with no audio; stop and play the complete MP4.
- [ ] Record a selected region, including an odd-pixel rectangle; verify even cropped dimensions and output bounds.
- [ ] Record microphone in MP4 and MP3; verify voice and playback duration.
- [ ] Record speaker audio in MP4 and MP3; repeat using Bluetooth output and a USB headset as default devices.
- [ ] Cancel screen sharing, deny a picker, close a source window, and stop a recording during preparation.
- [ ] Stop after five minutes and verify MP4 seeks and has a complete trailer using `ffprobe` or a media player.
- [ ] Verify filenames containing spaces, quotes and Unicode; verify permission/disk-full errors.
- [ ] Verify local OCR with synthetic text and unavailable Tesseract.
- [ ] Confirm closing protects an unsaved image and never destroys a running capture worker.

Record machine/session versions and outcomes before marking this release desktop-validated.

## Angular 0.2 desktop integration check

Angular 22 AOT compilation and library linking pass. `docs/render_angular.py` launched the real offline Qt WebEngine desktop window and verified native bridge connection, loading a synthetic image into the native engine, a pointer-driven rectangle annotation, native clipboard copy, and undo/redo state. It rendered the editor, idle recording setup and workflows. This is a scoped application check, not a real GNOME/Wayland recording test.

The environment emitted expected offscreen GPU/D-Bus/udev warnings. These do not establish that native desktop capture, sound routing or video encoding work.
