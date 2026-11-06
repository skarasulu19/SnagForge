#!/usr/bin/env bash
# User explicitly requested a PUBLIC, open-source repository.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
command -v gh >/dev/null || { printf '%s\n' 'Install GitHub CLI: sudo apt install gh'; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login
if [[ ! -d .git ]]; then
  git init -b main
  git add .
  git commit -m 'Initial SnagForge alpha: capture, annotations, recording, and manual'
fi
if git remote get-url origin >/dev/null 2>&1; then
  printf '%s\n' 'An origin remote already exists. Inspect it before publishing.' >&2
  exit 1
fi
gh repo create SnagForge --public --source=. --remote=origin --push \
  --description 'Capture. Annotate. Explain. Open-source screenshot and recording workbench for Ubuntu.'
gh repo view --web
