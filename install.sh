#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "--system-deps" ]]; then
  sudo apt-get update
  sudo apt-get install -y python3-venv python3-pip libxcb-cursor0 libegl1 libopengl0 \
    xdg-desktop-portal xdg-desktop-portal-gnome \
    gstreamer1.0-tools gstreamer1.0-pipewire gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav pulseaudio-utils tesseract-ocr
fi
python3 -m venv "$project_dir/.venv"
"$project_dir/.venv/bin/python" -m pip install -r "$project_dir/requirements.txt"
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
"$project_dir/.venv/bin/python" - "$project_dir" <<'PY'
import pathlib, shlex, sys
root=pathlib.Path(sys.argv[1])
launcher=pathlib.Path.home()/'.local/bin/snagforge'
launcher.write_text('#!/bin/sh\nexec '+shlex.quote(str(root/'.venv/bin/python'))+' '+shlex.quote(str(root/'app.py'))+' "$@"\n')
launcher.chmod(0o755)
def desktop_quote(value):
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'
desktop=pathlib.Path.home()/'.local/share/applications/snagforge.desktop'
desktop.write_text('[Desktop Entry]\nType=Application\nName=SnagForge\nComment=Capture. Annotate. Explain.\nExec='+desktop_quote(launcher)+'\nIcon=camera-photo\nTerminal=false\nCategories=Graphics;AudioVideo;\nStartupNotify=true\n')
PY
printf '%s\n' 'Installed. Launch SnagForge from Applications, or run ~/.local/bin/snagforge.'
