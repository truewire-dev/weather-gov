#!/usr/bin/env bash
# TRU-1045 Rust review probes. Usage: run.sh <weather-gov checkout at a PR head>
# review_wire.rs          (#15)  exact query on the wire: id=KSEA%2CKPDX
# review_published_paths  (#13)  rust-v0.2.0 paths fail to compile (E0432/E0603)
# review_live_radar.rs    (#18/#20, live network, --ignored) decode a live radar sweep
# review_live_products.rs (#13, live network, --ignored) decode a live products sweep
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); repo=$1
cp "$here"/review_*.rs "$repo/packages/rust/tests/"
cd "$repo/packages/rust"
for t in "$here"/review_*.rs; do t=$(basename "$t" .rs)
  echo "== $t"; cargo test --offline --test "$t" -- --include-ignored --nocapture || true
done
