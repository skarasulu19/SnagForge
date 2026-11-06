# SnagForge: Snagit + ShareX workflows for Ubuntu

Requested direction, 6 November 2026. This is a development roadmap, not a list of shipped features.

## Product direction

Combine an approachable screenshot editor and visual documentation workflow with configurable after-capture automation and small image/video utilities. Use native Ubuntu capture interfaces. Keep local saving as the default; sharing destinations are opt-in.

## Feature priorities

| Priority | Workflow | Reference inspiration | Current state / next work |
|---|---|---|---|
| P0 | Reliable screen, window and selected-region recording | Both | MP4 recording code exists; validate on Ubuntu 26 GNOME/Wayland, scaling, cancellation and long recordings |
| P0 | Sound routing and recording controls | Snagit | Mic OR system audio exists; add simultaneous mixing, meters, pause/resume and background stop control |
| P1 | Smart scrolling capture | Both | Manual vertical stitching exists; add overlap detection, seam preview, sticky-header handling and horizontal stitching |
| P1 | Editable screenshot annotations | Both | Raster annotations exist; add movable shapes/text, callouts, stamps and a saved project format |
| P1 | After-capture workflows | ShareX | Three local presets delivered in 0.2; configurable task chains remain future work |
| P1 | Recording and GIF utilities | Both | Add trim, frame extraction, clip joining and GIF export |
| P1 | Searchable local history | Both | Filename search delivered in 0.2; thumbnails, tags and project metadata remain future work |
| P2 | Pin screenshot to desktop | ShareX | Reference window delivered in 0.2; validate always-on-top behavior on GNOME/Wayland |
| P2 | Image utility toolbox | ShareX | Add batch resize/convert, image combine/compare, color picker and QR generation/reading |
| P2 | Capture shortcuts and reusable regions | ShareX | Use supported desktop shortcuts/portals; test global capture/stop and per-monitor scaling |
| P2 | Visual how-to guides | Snagit | Add step collection, captions, templates and PDF/HTML export; evaluate click recording under Wayland permissions |
| P2 | Webcam and cursor presentation | Snagit | Add webcam overlay, cursor emphasis and click indicators where platform metadata permits |
| P3 | Local assistance | Snagit | Evaluate OCR replacement, suggested redactions and noise reduction; extraction-only OCR exists today |
| P3 | Optional sharing integrations | ShareX | Add user-configured destinations with explicit upload actions, progress and credential management |

## Ubuntu recording targets

Start acceptance testing with 1080p / 30 fps and H.264 MP4. Treat 60 fps, 1440p, 4K and hardware encoding as configurable targets that depend on actual GPU, drivers and compositor behavior. The alpha currently uses software x264 at 30 fps. No frame-rate, latency or CPU-use benchmarks have been measured on the user's machine.

Use the ScreenCast desktop portal and PipeWire for supported screen/window selection, then crop/encode in the media pipeline. Screen permission and audio-device routing are separate concerns. Test speaker, Bluetooth and USB-headset defaults independently. Automatic scrolling, global input observation and always-on-top windows require desktop-specific validation.

## Reference sources

- Official Snagit features: https://www.techsmith.com/snagit/features/
- Official Snagit changelog: https://www.techsmith.com/snagit/whats-new/
- Official ShareX feature list: https://getsharex.com/
- Ubuntu 26.04 recording documentation: https://ubuntu.com/desktop/docs/en/26.04/how-to/record-the-screen/
- ScreenCast portal specification: https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html
- Additional workflow reference requested by the user: https://snagitpro.com/ (independent educational site)

Use these as workflow references. SnagForge is an independent application; this plan does not include copying proprietary source, branding or assets.
