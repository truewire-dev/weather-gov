#!/bin/bash
# TRU-541 probes against weather-gov PR #14 at 1b8a646 (Rust). Each probe is user code;
# the table says whether it should compile at this head and, if not, which error it gives.
# Needs typed crates/truewire-core (TYPED=<typed checkout>): crates.io 0.1.0 has no Seek (TRU-46).
# Usage: TYPED=/path/to/typed review/TRU-541/check.sh   (exit 0 = every probe as expected)
set -u
root=$(cd "$(dirname "$0")/../.." && pwd)
cd "$root/packages/rust"
patch="patch.crates-io.truewire-core.path=\"${TYPED:?set TYPED}/crates/truewire-core\""
cargo update --offline -q -p truewire-core --config "$patch" || cargo update -q -p truewire-core --config "$patch"
status=0
while read -r probe want; do
  cp "$root/review/TRU-541/$probe.rs" tests/
  if cargo check --offline -q --config "$patch" --test "$probe" 2>"/tmp/tru541-$probe.err"; then
    got=pass
  else
    got=$(grep -m1 -oE '^error\[E[0-9]+\]' "/tmp/tru541-$probe.err" | tr -d 'error[]')
    got=${got:-error}
  fi
  rm "tests/$probe.rs"
  if [ "$got" = "$want" ]; then mark=ok; else mark=UNEXPECTED; status=1; fi
  printf '%-10s %-34s want %-6s got %s\n' "$mark" "$probe" "$want" "$got"
done <<'TABLE'
review_zone_kind pass
moved_new_paths pass
moved_observationcollection E0603
moved_stationcollection E0603
moved_observationcollectiontype E0432
moved_observationpagination E0432
moved_stationcollectiontype E0432
moved_collectionpagination E0432
review_zone_kind_response E0308
review_required_enum E0277
review_zone_geometry E0308
TABLE
git checkout -q -- Cargo.lock
exit $status
