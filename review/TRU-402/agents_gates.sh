#!/bin/sh
# TRU-402: do the AGENTS.md "Gates" catch what CI's gates job catches?
# Run from the repository root on a clean tree. TRUEWIRE is the truewire command
# (default: truewire on PATH); RUFF likewise. Exits 1 while the finding holds: a spec edit
# with no regeneration and a lint error pass every AGENTS.md gate but fail CI.
set -u
TRUEWIRE=${TRUEWIRE:-truewire}
RUFF=${RUFF:-ruff}
trap 'git checkout -q -- spec packages/python/test/test_spec.py' EXIT
sed -i 's/about 300 observations/about 300 observations (edited)/' \
  spec/endpoints/stations/get_observations/endpoint.json
printf 'x = 1\nimport os\n' >> packages/python/test/test_spec.py
agents=0
for gate in "check" "standards" "docs check" "docs lint" "examples --require-verified"; do
  $TRUEWIRE $gate >/dev/null 2>&1; rc=$?
  [ $rc -eq 0 ] || agents=1
  echo "AGENTS.md gate: truewire $gate -> $rc"
done
$TRUEWIRE generate python --check >/dev/null 2>&1; ci_gen=$?
echo "ci.yml gate: truewire generate python --check -> $ci_gen"
$RUFF check --config packages/python/ruff.toml packages/python/src packages/python/test >/dev/null 2>&1; ci_ruff=$?
echo "ci.yml gate: ruff check -> $ci_ruff"
if [ $agents -eq 0 ] && { [ $ci_gen -ne 0 ] || [ $ci_ruff -ne 0 ]; }; then
  echo "FINDING HOLDS: every AGENTS.md gate passed, CI's gates job fails"; exit 1
fi
echo "OK: the AGENTS.md gates catch what CI catches"
