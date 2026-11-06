#!/usr/bin/env bash
# Detach from the terminal; keep diagnostics in a predictable local log.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
  printf '%s\n' 'Run ./install.sh --system-deps first.' >&2
  exit 1
fi
log_dir="${XDG_STATE_HOME:-$HOME/.local/state}/SnagForge"
mkdir -p -- "$log_dir"
nohup "$project_dir/.venv/bin/python" "$project_dir/app.py" "$@" </dev/null >>"$log_dir/snagforge.log" 2>&1 &
printf 'SnagForge started in the background. Log: %s\n' "$log_dir/snagforge.log"
