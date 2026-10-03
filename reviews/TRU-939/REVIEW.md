# Rust review of weather-gov PR #15

Reviewed head: `962d665bb65e8f4020d87eb487cf15d489ec0ad5`.
Declared base: `agent/TRU-5`, `e548d4969ed176d87cb8654a47ff771db96c11ea`.
Date: 2026-10-03. No merge authorized for this multi-reviewer PR.

**Code-review verdict: APPROVE the Rust array-filter delta at this exact head.**
This is not test approval or merge approval. The full Rust mock-backed suite and
the additional Rust consumer tests have NOT run: the shared build lane is occupied.
The review task remains blocked until those checks run. Changed base/pins require
renewed review as directed by the Lead.

No new correctness, simplicity, elegance, or DX findings in the Rust delta.

| Severity | Where | What | Evidence | Suggested fix |
| --- | --- | --- | --- | --- |
| blocker (existing integration) | `packages/python/pyproject.toml:26`, `packages/rust/Cargo.toml:24`, `packages/rust/Cargo.lock` | The committed dependencies are not the published-runtime overlay reviewed here. Exact-head verification is still required before merge. | CLI is pinned to `0.10.0`; Cargo requires `0.1` and locks core `0.1.0`. The assignment reports failed PR verify. With CLI `0.11.0`, `generate rust --check` exits 1 and reports `out of date: client.rs`. No committed-pin Rust test pass is claimed. | Lead integrates base/pins through [TRU-409](/TRU/issues/TRU-409) and [TRU-916](/TRU/issues/TRU-916), regenerates as needed, and obtains current-head verification/review. Already owned; no duplicate ticket. |

## Source and recording review

- `Core::request` still handles path placeholders before query fields. Nulls and empty
  arrays emit no pair. Nonempty arrays use `plain` on each item, join once with `,`,
  then pass a single pair to `RequestOptions::query`. Strings retain their content;
  numbers and booleans retain JSON scalar rendering. HTTP query encoding handles
  reserved characters. No new casts, error handling, resource ownership, or async state.
- All 17 array fields across the four affected endpoints have `match.query_arrays=comma`.
  Their generated request fields remain `Option<Vec<String>>` or `Option<Vec<Enum>>`;
  serde enum spellings remain intact. The generated endpoint changes are documentation
  only. No response type or numeric representation changes in the diff.
- The station recording contains exactly `KPDX` and `KSEA`, with typed station identifiers,
  numeric elevation/coordinates, and the existing collection envelope.
- The zone recording contains exactly `WAC033` (county) and `WAZ315` (public), with null
  geometry, ISO dates, nullable radar station, and observation-station arrays.
- Both new Rust replay tests require two request IDs and compare sorted complete returned
  ID vectors against them. This rejects missing IDs, duplicates, and extra IDs. The zone
  test additionally checks County/Public types. These assertions were read, not executed.
- Existing Rust request usage stays direct: `Request { id: Some(vec!["KSEA".into(),
  "KPDX".into()]), ..Default::default() }`; callers do not need to join strings themselves.

## Executed checks

- CLI 0.11.0 `check --project <isolated-client>`: exit 0, `Result: OK`, 19 endpoints,
  23 examples, zero validation errors/authoring violations, three warnings.
- CLI 0.11.0 `generate rust --check --project <isolated-client>`: exit 1,
  `Generated files for weather_gov differ from the plan: - out of date: client.rs`.
  No regenerated code was substituted into the test candidate.
- `venv/bin/python reviews/TRU-939/probe_mock.py <isolated-client>`: exit 0.
  Real loopback HTTP calls return both station IDs and both zone IDs. Both endpoints
  reject separate repeated IDs and comma-plus-duplicate-key forms with HTTP 422
  `unexpected_parameters`. See `mock-results.txt`.
- Five additional published mock matcher checks pass: empty arrays omit the key;
  an explicit empty key does not match an empty array; boolean arrays match comma
  text and reject repeated keys; scalar false, integer limit, and a scalar string
  containing a comma match without treating the scalar as an array.
- Guarded Rust runner: exit 75, `BLOCKED: /home/truewire/verify/lock-main; no build started`.
  Earlier read-only inspection also found the shared `rust-build.lock` busy and an active
  bot Cargo/clippy process. No processes were stopped or bot checks rerun.

## Exact overlay and continuation

Scratch: `/home/truewire/work/scratch/TRU-939/` (retained while this task is open).
`client/` is `git archive` of the reviewed head. Only its Cargo manifest/lock were
overlaid: `truewire-core = "0.1"` becomes `"=0.2.0"`, followed by
`cargo update --manifest-path client/packages/rust/Cargo.toml -p truewire-core --precise 0.2.0`.
`published-overlay.patch` records the entire manifest/lock delta, including transitive
changes. There are no path patches or regenerated client files. Cargo uses the normal
registry cache; no fresh-install claim. The isolated venv installs PyPI
`truewire==0.11.0` and `truewire-core==0.3.0`. Python client and TS pins are untouched
and their suites are outside this review.

Coordinated on [TRU-922](/TRU/issues/TRU-922). Rust reviewer owns the next action when
the shared lanes are available:

```sh
python3 reviews/TRU-939/run_serial.py /home/truewire/work/scratch/TRU-939
```

The runner acquires all four shared locks nonblockingly, uses `CARGO_BUILD_JOBS=1`,
`RUSTFLAGS=-D warnings`, and serial test execution. It runs the full unmodified suite
first with `truewire test rust --project <isolated-client>` (published CLI uses a
positional language, not `--language`). Only after success does it copy `wire.rs` into
the isolated package and run four additional consumer tests against a TCP capture
server: all four changed endpoints, empty arrays, null omission, scalar integer/string,
boolean scalar/array extension fields, enum arrays, scalar comma, and path separation.
These added Rust tests are prepared but uncompiled/unexecuted; do not cite them as passes.

After the suite and probes run, publish exact results, update the verdict if warranted,
and close this task. Delete its scratch only after checking for dependent work/live
processes. Do not merge or publish.
