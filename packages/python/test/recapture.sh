#!/usr/bin/env sh
# Re-record every example in this project from the live weather.gov API with `truewire
# capture`. Run from anywhere; needs `truewire` and the package on the path
# (`pip install -e 'packages/python[dev]'`).
#
# No credentials at all. The National Weather Service answers every endpoint here to
# anyone who identifies themselves in `User-Agent`, which is why this showcase can be
# re-recorded by a GitHub runner on a schedule with nothing configured and no secret to
# leak. Nothing here is skipped for want of a credential, so an endpoint that does not
# record is a failure, full stop.
#
# The request half of each example (`examples/<id>.request.json`) is the source of truth:
# this script replays exactly those, so re-recording keeps the same ids and descriptions
# and only the responses move. Two of them go stale on their own and are repaired first --
# see `refresh_examples.py`.
#
# One example failing does not stop the rest. A live API will always have one endpoint
# having a bad day, and a recording run should bank what it was given and report the
# rest, so the pull request carries the recordings that did land. Failures are listed at
# the end and the exit code is non-zero, so the job still shows red.
cd "$(dirname "$0")/../../.." || exit 1
PYTHON=${PYTHON:-python3}
CONTACT=${CONTACT:-hello@truewire.dev}

failed=''
recorded=0

# Repaired before anything is captured rather than after a capture failed, because neither
# of these fails loudly: an expired observation window records as an empty
# `FeatureCollection` with a 200, which is a green recording of nothing.
if ! "$PYTHON" packages/python/test/refresh_examples.py; then
  failed="$failed packages/python/test/refresh_examples.py"
fi

capture_example() {
  request=$1
  function=$(echo "$request" | awk -F/ '{print $3 "." $4}')
  id=$(basename "$request" .request.json)
  description=$("$PYTHON" -c 'import json, sys; print(json.load(open(sys.argv[1])).get("description", ""))' "$request")
  parameters=$("$PYTHON" -c 'import json, sys; print(json.dumps(json.load(open(sys.argv[1]))["request"]))' "$request")
  truewire capture "$function" --id "$id" -d "$description" --request "$parameters" --new "contact=$CONTACT"
}

for request in spec/endpoints/*/*/examples/*.request.json; do
  if capture_example "$request"; then
    recorded=$((recorded + 1))
    continue
  fi
  failed="$failed $request"
done

echo
echo "recorded $recorded example(s)"
if [ -n "$failed" ]; then
  echo 'these did not record:'
  for request in $failed; do echo "  $request"; done
  exit 1
fi
