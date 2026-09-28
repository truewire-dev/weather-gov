# TRU-32 reproductions (Rust review of PR #10)

Needs the toolchain set up as in TRU-32, with `packages/rust/Cargo.toml` patched to
typed-port's `truewire-core` 0.1.1 (the patch is committed on this branch).

```
cd packages/rust
# 1. The walk against the recorded 76 KSEA observations, `end` inclusive as the spec says:
python3 ../../review/TRU-32/server.py ../../spec/endpoints/stations/get_observations/examples/ksea_window.response.json 8765 &
cargo run -q --example walk        # limit 1 -> LogicError; 2, 7, 10, None -> 76/76 rows
cargo run -q --example dispatch    # typo -> LogicError, `_paged` unreachable
kill %1
# 2. The same, `end` exclusive, as the live service behaves:
python3 ../../review/TRU-32/server_exclusive_end.py ../../spec/endpoints/stations/get_observations/examples/ksea_window.response.json 8765 &
cargo run -q --example walk        # every valid limit, 1 included -> 76/76 rows
kill %1
# 3. The README walk snippet proposed in the review compiles:
cargo build -q --example readme_walk
# 4. The committed lockfile does not build (truewire-core 0.1.0 has no Seek):
git checkout 9e8d082 -- Cargo.toml Cargo.lock && cargo check --lib   # E0432 Seek, SeekState
```

Live service, 2026-09-28: `end` is exclusive, `start` inclusive.
`?limit=3&end=2026-09-27T11:55:00Z` -> 11:53, 11:50, 11:45;
`?limit=3&end=2026-09-27T11:55:01Z` -> 11:55, 11:53, 11:50.
`?limit=1000` -> 400 "Must have a maximum value of 500".
