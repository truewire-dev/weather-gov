#!/usr/bin/env bash
# TRU-1316 Rust re-review probes for #13. Usage: run.sh <weather-gov checkout at a PR head>
# review_tru1316_paths  rust-v0.2.0 paths named in the CHANGELOG fail to compile (6 E0432, 4 E0603)
# review_tru1316_live   (live network, --ignored) all 338 types' location maps decode; two `type` filters both arrive
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd); repo=$1
cp "$here"/review_*.rs "$repo/packages/rust/tests/"
cd "$repo/packages/rust"
cargo test --offline --test review_tru1316_paths 2>&1 | grep -E '^error\[' || true
cargo test --offline --test review_tru1316_live -- --include-ignored --nocapture
