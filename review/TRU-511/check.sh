#!/usr/bin/env bash
# Review probes for weather-gov PR #14 (TRU-511). Usage, from the weather-gov root:
#   TYPED=<typed checkout> review/TRU-511/check.sh
# Installs the client NON-editable into a scratch venv, so pyright treats it as a library
# (py.typed), the way a user sees it.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
HERE=$ROOT/review/TRU-511
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
uv venv -q "$TMP/venv" --python 3.11
VIRTUAL_ENV=$TMP/venv uv pip install -q "$TYPED/packages/core-python"
VIRTUAL_ENV=$TMP/venv uv pip install -q --no-deps "$ROOT/packages/python"
cp "$HERE/imports.py" "$TMP/"
printf '{"venvPath": "%s", "venv": "venv", "typeCheckingMode": "standard"}\n' "$TMP" > "$TMP/pyrightconfig.json"
echo '== 1. old import paths under pyright (expect 0 errors, or the CHANGELOG not claiming they work)'
(cd "$TMP" && pyright imports.py) || true
# The claim is wrapped across two lines, so join them before matching.
if tr -s ' \n' ' ' < "$ROOT/packages/python/CHANGELOG.md" | grep -q 'old imports of the two collections still work'; then
  echo 'CHANGELOG: still claims the old imports work'
else
  echo 'CHANGELOG: claim gone'
fi
echo '== 2. positional argument of the one-zone endpoints (expect zone_id)'
"$TMP/venv/bin/python" "$HERE/call_shape.py"
