#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
  printf '%s\n' 'Run ./install.sh --system-deps first.' >&2
  exit 1
fi
exec "$project_dir/.venv/bin/python" "$project_dir/app.py" "$@"
