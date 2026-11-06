# Feature map and roadmap

The comparison reference is [TechSmith's Snagit features page](https://www.techsmith.com/snagit/features/), reviewed 6 November 2026. This document groups capabilities rather than promising full parity. No TechSmith source code, assets, templates or branding are included.

| Workflow | SnagForge 0.1 alpha | Remaining work |
|---|---|---|
| Screenshot capture | Portal picker and rectangle selection on returned preview | Live desktop overlay, presets, multi-region capture |
| Capture delay | 0–30 seconds before portal picker | Capture presets and time-lapse |
| Scrolling windows | Guided vertical stitching with manual fixed overlap | Auto scroll, overlap detection, horizontal panorama |
| Recording | MP4 screen/window/region; MP3 audio-only | Real Ubuntu acceptance, pause/resume, webcam overlay |
| Sound | Mic/default input OR system output | Mixing, meters, noise reduction |
| Annotations | Arrows, pen, shapes, text, numbered steps, highlight | Callouts, stamps, themes, editable objects |
| Attention/privacy | Spotlight, pixelation, opaque redaction | Smart detection/redaction and magnifier |
| Image editing | Crop, proportional resize, rotate, undo/redo | Borders, cut-out, background removal, smart object movement |
| OCR | Tesseract extraction and clipboard copy | Language controls, editable replacement text |
| Video editing | None | Trim, combine, GIF, extracted frames, narrated image videos |
| Steps/guides | Manual numbered annotation | Automatic click recording and guide templates |
| Organization | Recent default-folder exports | Tags, search, collections, persistent metadata |
| File formats | PNG, JPEG, WebP, MP4, MP3 | PDF export, editable project format, batch processing |
| Sharing | Local files and clipboard | Optional user-controlled share integrations |
| Shortcuts | Focused-app shortcuts; OS launcher shortcut documented | Dedicated global capture/stop shortcuts |
| Collaboration / AI | None | Separate design work; no cloud service implied |

## Next milestones

1. Validate live Ubuntu 26 GNOME/Wayland capture, MP4 finalization, sound routing and region cropping across multiple monitors and scaling levels.
2. Improve recording lifecycle: stop control without foregrounding the captured screen, session-closed events, pause, level meters and audio mixing.
3. Implement automatic overlap detection with a seam confidence preview and guided correction; consider opt-in platform-specific automatic scrolling.
4. Add searchable local project history, editable annotations, video trimming and GIF export.
5. Evaluate webcam capture, guide generation and local assistive features after desktop behavior is stable.

Only milestone 1 is a prerequisite for promoting this alpha to a desktop-validated release. Other milestones are plans, not delivered features.

## Release-history audit — 6 November 2026

Reviewed TechSmith's [current changelog](https://www.techsmith.com/snagit/whats-new/), [Windows 2026 history](https://support.techsmith.com/hc/en-us/articles/42674936732685-Snagit-Windows-2026-Version-History) and [Mac 2026 history](https://support.techsmith.com/hc/en-us/articles/41975263481613-Snagit-Mac-2026-Version-History). These references are a comparison baseline, not features delivered by SnagForge.

Additional gaps include automatic click-to-guide recording and editable PowerPoint slide export, Camtasia Online collaboration, recording duration limits, simultaneous microphone/system audio with meters, and noise reduction. SnagForge currently has no cloud integration, and no such service is required to use the alpha.

The current capture path selects a rectangle on a captured preview, not a live screen overlay. Scrolling is manual vertical stitching with fixed overlap, not automatic scrolling or automatic alignment. Editor annotations are flattened into image pixels, not movable objects. Local OCR extracts text without replacing it in the image. These distinctions must remain explicit in release notes.

## Workflow reference

The user also requested similar workflows to those described on [SnagitPro](https://snagitpro.com/), an independent educational resource rather than the official Snagit product site. The feature baseline remains TechSmith's official documentation. Relevant targets include scrolling capture, screenshot annotation and stamps, redaction, OCR, screen recording, visual SOP creation, multi-monitor selection, and accessible screenshot descriptions. This section records requested scope; it does not mark those capabilities complete.
