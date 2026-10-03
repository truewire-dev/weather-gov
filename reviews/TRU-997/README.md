# Rust review checkpoint — PR #16

Target: `bbacd5055ee11bf8d715321ba63c2116cd0a97a0`.
Generator and diagnostic Rust core: `62ed93389566d8bf540237a8204dd07fb69bfe46`.
Review is **in progress**; no approval or final PR review has been issued.

The assigned `agent/TRU-997` branch imports the exact client tree in `69d7a217`;
its tree hash equals the target's `aa7816c1f6b9a4e553eb32568f740ed0ee18a0f3`.
Only this review directory is added afterwards. No client dependency is changed.

## Evidence inspected

- Fresh `truewire generate rust --check` using the merged generator: `Generated files match the plan for weather_gov (41 files).`
- All 150 tracked Rust/spec files match the transferred diagnostic copy byte for byte, excluding only its explicitly substituted Cargo.toml/Cargo.lock.
- Spec, recordings, and dependency files are unchanged from pre-regeneration `b90c998`; that baseline already includes the TypeScript integration.
- Generator checkout HEAD is `62ed93389`, with no tracked modifications. Runtime is local core 0.2.0; committed runtime is registry core 0.1.0. Toolchain is rustc 1.98.1 (48a229cea), cargo 1.98.1 (797e8a9bc).
- Read the transferred full diagnostic suite/build/probe logs: 31 passing tests (25 replay, 4 shared types, 1 positive headline lookup, 1 README compilation test), zero ignored. Tests and consumer coverage inspected. Required Zone geometry rejects missing and accepts null; Alert geometry preserves absent/null/value; ZoneKind is shared; all four graph collections use at_graph. Headline id and at_id remain distinct.
- Read the prior consumer/migration bundle at typed `8fc1f69d567439f98474098769c85402c631aa1d`. The integrated consumer correctly adapts historical ZoneType to the actual ZoneKind schema.
- Recorded wire bodies inspected: office headlines, null briefing, weather stories, TAFs, radio transmitter, and zone polygon. Required-nullable scalar serde and geometry attributes inspected in generated source.
- GitHub confirms PR head bbacd505, base e548d496, and `truewire/verify: failure` (5/5 gates). Original published-core compiler log reports E0432 on Seek/SeekState. Diagnostic passes do not clear that failure.

## Findings to include in final review

| Severity | Where | What | Evidence | Suggested fix |
| --- | --- | --- | --- | --- |
| blocker | packages/rust/Cargo.toml; src/weather_gov/stations/get_observations.rs:10 and stations/mod.rs:18 | Committed runtime cannot compile the client. This predates this regeneration and remains a delivery blocker. | Transferred `rust-published.log`: registry core 0.1.0, E0432 unresolved Seek/SeekState. Check: `RUSTFLAGS='-D warnings' CARGO_BUILD_JOBS=1 cargo test --locked --test probe_tru598 --no-run` in packages/rust. | Lead must resolve runtime/toolchain compatibility through the authorized integration path. Current prohibition on pin edits remains. |
| should | packages/rust/CHANGELOG.md:40–41 | The package's unreleased notes still describe @id as id and the natural id as id2, contradicting the generated API and root migration. | Before, following the package notes: `let token = &headline.id2; let url = &headline.id;`. Actual API: `let token = &headline.id; let url = &headline.at_id;`. `types/mod.rs:81–87` defines only at_id/id. `old_id2.rs` is a pending compiler reproduction. | Correct the package changelog and include or link the complete naming/geometry migration there. |

Lead owns routing fixes; this review will not merge, release, publish, or alter pins.

## Pending native probes and capacity

`consumer.rs` adds required-nullable scalar checks (headline summary, briefing,
weather-story download, measurement value) and complete TAF/headline JSON-LD
round trips. `old_id2.rs` exercises the stale package changelog's field name.
Neither new probe has been executed yet.

The first nonblocking attempt failed on `/home/truewire/verify/lock`. All acquired
locks were released, no native job started, and no other job was interrupted.
Runner: `/home/truewire/work/scratch/TRU-997/run-review.py`. It tries all four locks,
then serially runs the published build, diagnostic consumer, and old-id2 compiler
probe with nice 19, one Cargo job and `-D warnings`. Commands have 300-second limits.

Diagnostic fixtures and logs live at
`/home/truewire/work/scratch/TRU-997/from-TRU-609/`. The original handoff evidence is
also attached to the ticket as attachment `19fa9ac9-3086-424c-aba6-4093be414507`.
The committed product manifest remains untouched; the diagnostic copy alone uses
the local runtime path. Do not report those results as published-pin success.
