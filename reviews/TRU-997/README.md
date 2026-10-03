# Rust review — PR #16 at bbacd505

Target: `bbacd5055ee11bf8d715321ba63c2116cd0a97a0`.
Generator and diagnostic Rust core: `62ed93389566d8bf540237a8204dd07fb69bfe46`.
Verdict: **CHANGES REQUESTED**. This closes the review assignment, not the delivery blockers.

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

## Findings

| Severity | Where | What | Evidence | Suggested fix |
| --- | --- | --- | --- | --- |
| blocker | packages/rust/Cargo.toml; src/weather_gov/stations/get_observations.rs:10 and stations/mod.rs:18 | Committed runtime cannot compile the client. This predates this regeneration and remains a delivery blocker. | Transferred `rust-published.log`: registry core 0.1.0, E0432 unresolved Seek/SeekState. Check: `RUSTFLAGS='-D warnings' CARGO_BUILD_JOBS=1 cargo test --locked --test probe_tru598 --no-run` in packages/rust. | Lead must resolve runtime/toolchain compatibility through the authorized integration path. Current prohibition on pin edits remains. |
| should | packages/rust/CHANGELOG.md:40–41 | The package's unreleased notes still describe @id as id and the natural id as id2, contradicting the generated API and root migration. | Before, following the package notes: `let token = &headline.id2; let url = &headline.id;`. Actual API: `let token = &headline.id; let url = &headline.at_id;`. `types/mod.rs:81–87` defines only at_id/id. `old_id2.rs` is an unexecuted supplemental compiler reproduction; the finding is supported by the before/after API snippet and source. | Correct the package changelog and include or link the complete naming/geometry migration there. |

Lead owns routing fixes; this review will not merge, release, publish, or alter pins.

## Coverage limits and retained evidence

The complete existing suite is reused under the assignment's exact-input rule:
client/spec byte identity and generator/runtime revisions were checked, and the
31-test coverage/logs were inspected. No fresh native pass is claimed.

`consumer.rs` adds required-nullable scalar checks (headline summary, briefing,
weather-story download, measurement value) and complete TAF/headline JSON-LD
round trips. `old_id2.rs` exercises the stale package changelog's field name.
These supplemental probes were not executed: the initial attempt and all three
bounded continuations exited 75 at the occupied `/home/truewire/verify/lock`.
Every attempt released acquired locks immediately. No native job started, and
no other job was interrupted. The capacity continuation is now exhausted.
The existing evidence already establishes both findings; no new pass/failure is
inferred for these extra probes.

At final review, PR #16 has advanced to
`3f5f34f6258fba45e7cbbd20969d9df2b118b368`. The GitHub comparison shows only the
three vendored language rule files changed. This verdict is explicitly bound to
requested head `bbacd5055ee11bf8d715321ba63c2116cd0a97a0`; it is not an approval of
the newer head. No Go package is configured, and no new Go rendering was performed
in this Rust review.

The original full handoff logs are attachment
`19fa9ac9-3086-424c-aba6-4093be414507`. Copies of the Rust suite/build log and
published compiler error excerpt are beside this report under `evidence/`.

Before closing the review, process inspection found no live process referencing
its scratch. The parent delivery ticket and Go review remain open and may need
the shared toolchain/consumer bundle. All retained scratch was transferred to
`/home/truewire/work/scratch/TRU-466/from-TRU-997/`; the linked toolchain was moved
with `git worktree move`, and the former ticket scratch directory was removed.
The diagnostic Cargo path and saved runner were updated to the new prefix.

The saved runner is now
`/home/truewire/work/scratch/TRU-466/from-TRU-997/run-review.py`. It tries all four
locks nonblocking and runs commands serially with nice 19, one Cargo job,
`-D warnings`, and 300-second limits. It is retained for the Lead; no retry is
scheduled by this closed review.

No client dependency pins, generated client code, or recordings were edited by
this review. Lead owns routing the fixes and all integration/merge decisions.

**CHANGES REQUESTED**
