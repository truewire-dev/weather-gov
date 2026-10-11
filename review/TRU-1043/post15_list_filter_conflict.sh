#!/usr/bin/env bash
# TRU-1043: after #15 lands, #13 and #18 each fail #15's list-filter guard.
# Usage: from a weather-gov checkout with a .venv holding truewire==0.11.0:
#   review/TRU-1043/post15_list_filter_conflict.sh <scratch-dir>
set -euo pipefail
S=${1:?scratch dir}
git fetch -q origin 'refs/pull/*/head:refs/remotes/pr/*'
for next in 13 18; do
  git worktree add -q --detach "$S/m15-$next" origin/main
  ( cd "$S/m15-$next"
    git -c user.name=t -c user.email=t@t merge -q --no-ff --no-edit pr/15
    git -c user.name=t -c user.email=t@t merge -q --no-ff --no-edit "pr/$next"
    echo "== main + #15 + #$next"
    PYTHONPATH=$PWD/packages/python/src "$OLDPWD/.venv/bin/python" -m pytest packages/python/test/test_spec.py -q -p no:cacheprovider | tail -3 || true )
  git worktree remove --force "$S/m15-$next"
done
