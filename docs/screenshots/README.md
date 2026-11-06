# UI screenshot provenance

All images use synthetic demonstration content and contain no personal captures.

- `01`–`04`: actual native Qt fallback editor and capture dialogs, rendered offscreen with `docs/render_screenshots.py`.
- `05`–`07`: actual Angular desktop editor, idle recording screen and local workflows, hosted in Qt WebEngine and rendered by `docs/render_angular.py`.

The Angular check verifies bridge connection, image sync, pointer-driven annotation, native clipboard copy and undo/redo. None of these screenshots demonstrates successful live screen/audio recording.

From the project root:

```bash
QT_QPA_PLATFORM=offscreen python docs/render_screenshots.py
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python docs/render_angular.py
```
