# Contributing

Start with the validation checklist and feature roadmap in `docs/`. This is an alpha; desktop capture fixes are the priority.

Set up the local Python environment using README.md. Run `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v`. For capture/recording changes, include actual Ubuntu GNOME/Wayland results, encoding/playback evidence and reproduction steps. Headless unit tests alone are insufficient.

Use synthetic captures in tests and documentation. Do not include personal screenshots, recordings, credentials or machine-specific logs. Keep media subprocess calls as argument arrays and do not interpolate user paths into shell commands. New features should have an honest README/manual entry distinguishing implemented behavior from plans.

Contributions are submitted under the project's GPL-3.0 license. Dependency licenses remain their own. No copied proprietary code, artwork or templates.
