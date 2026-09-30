#!/usr/bin/env bash
# Delta probes for weather-gov PR #14 at 1b8a646 (TRU-540). From the weather-gov root:
#   TYPED=<typed checkout> review/TRU-540/check.sh
# user.py: the new zone call shape type-checks, the old one (zone_type first) is refused.
# live.py: the three one-zone endpoints against api.weather.gov with a contact User-Agent.
set -euo pipefail
ROOT=$(git rev-parse --show-toplevel)
HERE=$ROOT/review/TRU-540
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
uv venv -q "$TMP/venv" --python 3.11
VIRTUAL_ENV=$TMP/venv uv pip install -q "$TYPED/packages/core-python"
VIRTUAL_ENV=$TMP/venv uv pip install -q --no-deps "$ROOT/packages/python"
cp "$HERE/user.py" "$TMP/"
printf '{"venvPath": "%s", "venv": "venv", "typeCheckingMode": "standard"}\n' "$TMP" > "$TMP/pyrightconfig.json"
echo '== user code (expect exactly 2 errors, on the two old_shape lines)'
(cd "$TMP" && pyright user.py) || true
echo '== live'
"$TMP/venv/bin/python" "$HERE/live.py"
