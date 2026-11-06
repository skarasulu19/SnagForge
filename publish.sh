#!/usr/bin/env bash
# Publish intentional source updates to the existing SnagForge repository.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
command -v gh >/dev/null || { printf '%s\n' 'Install GitHub CLI: sudo apt install gh'; exit 1; }
git rev-parse --verify HEAD >/dev/null 2>&1 || { printf '%s\n' 'Clone https://github.com/skarasulu19/SnagForge first, then run this script in that checkout.'; exit 1; }
origin_url="$(git remote get-url origin)"
case "$origin_url" in
  https://github.com/skarasulu19/SnagForge.git|git@github.com:skarasulu19/SnagForge.git) ;;
  *) printf '%s\n' 'Origin does not match the SnagForge repository. Inspect it before publishing.' >&2; exit 1 ;;
esac
gh auth status >/dev/null 2>&1 || gh auth login
git add .
if ! git diff --cached --quiet; then
  git diff --cached --stat
  git commit -m 'Update SnagForge application and documentation'
fi
git push origin HEAD:main
