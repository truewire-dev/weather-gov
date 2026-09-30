#!/bin/bash
# TRU-513 probes against weather-gov PR #14. Each probe is user code that should compile;
# on c85390f each fails. Needs typed crates/truewire-core (TYPED=<typed checkout>) since
# crates.io truewire-core 0.1.0 has no Seek (TRU-46).
# Usage: TYPED=/path/to/typed review/TRU-513/check.sh
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root/packages/rust"
patch="patch.crates-io.truewire-core.path=\"${TYPED:?set TYPED}/crates/truewire-core\""
cargo update --offline -q -p truewire-core@0.1.0 --config "$patch" || cargo update -q -p truewire-core@0.1.0 --config "$patch"
status=0
for probe in review_zone_kind review_zone_geometry review_moved_paths review_required_enum; do
  cp "$root/review/TRU-513/$probe.rs" tests/
  if cargo check --offline -q --config "$patch" --test "$probe" 2>"/tmp/$probe.err"; then
    echo "PASS $probe"
  else
    echo "FAIL $probe: $(grep -m1 -E '^error' "/tmp/$probe.err")"
    status=1
  fi
  rm "tests/$probe.rs"
done
git checkout -q -- Cargo.lock
exit $status
