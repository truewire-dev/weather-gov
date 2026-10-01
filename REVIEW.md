# Aviation review

Reviewed 2026-10-01 against `agent/TRU-5` at `e548d49`, implementation head `29bc351`.
Toolchain: typed `origin/truewire` at `c1d4c279`.

Verdict: **hold the merge**. The aviation acceptance checks pass. Language
review verdicts, verification of the committed dependencies, and a successful
`truewire/verify` status on the final PR head remain required.

## Checks run by the Lead

| Check | Result |
| --- | --- |
| `truewire check` | `Result: OK`; 26 endpoints, 28 examples, 0 validation errors, 4 authoring warnings |
| `truewire examples --require-verified` | 26/26 paired; 28 requests, 28 responses, all status 200 |
| S1 under `python -W error` | `fail`: `37/37 endpoints; inventory not approved`; no warning or unresolved endpoint |
| `truewire surface` | `Callables: 26 generated, 0 hand-written, 0 declared absent, over 26 spec(s)` |
| `truewire standards` | All mechanically enforced checks pass, including all three surfaces, docs check and docs lint |
| `truewire standards --only links` | `links` OK; no link warnings |
| `truewire generate python --check` | Generated files match the plan (37 files) |
| `truewire generate typescript --check` | Generated files match the plan (38 files) |
| `truewire generate rust --check` | Generated files match the plan (39 files) |
| `truewire score --verbose` | Exit 1: `6 pass, 4 fail, 2 unchecked -> not done` |
| Python test and lint rows | Both pass with the source runtime/toolchain |
| TypeScript test and lint rows | Both pass with the installed source runtime |
| Rust test row | `cargo test exited 101`: unresolved `truewire_core::Seek` and `SeekState` |
| Rust lint row | Format passes; clippy exits 101 on the same missing imports |

The other failing score rows are unapproved inventory and the unpublished Rust
package version 0.3.0. Conformance and stranger are unchecked. This is not a
complete B1 score. Rust failures originate in the existing observation walker,
with the committed lockfile resolving `truewire-core` 0.1.0. No runtime override
was applied for this score run. The score's Rust test command uses its default
build flags; it failed compilation, so no Rust test pass is claimed.

These checks use the source toolchain. The existing Python environment imports
that checkout; the existing TypeScript installation contains `@truewire/core`
0.2.0, although the committed manifest asks for `^0.1.1`. Results from this
environment do not establish that a clean installation of the committed pins
works. The implementation report's Rust run renamed a source runtime to
0.1.99; that is not evidence for the committed Rust dependency either.

## Recordings and specification

Read all seven aviation recordings: `get_cwsu/seattle`, `get_cwa/latest`,
`get_sigmet/anchorage_latest`, `list_cwas/fort_worth`,
`list_sigmets/convective_1e`, `list_sigmets_for_atsu/anchorage`, and
`list_sigmets_for_atsu_on_date/anchorage`. The collections hold 16, 7, 24 and
3 features respectively. All seven inventory method/path pairs match the
captured upstream OpenAPI, including the `cwsuId` placeholder spelling.
Inventory approval remains null; 37 entries are not the complete upstream API.

- `AdvisoryPolygon` preserves the recorded latitude-first coordinates. The
  Anchorage recording contains longitude -190.7. Reusing the ordinary
  longitude-first geometry type or normalizing its coordinates would change
  the wire data. The replay assertions check geographic bounds and closed rings.
- Returning the entire advisory feature preserves its meaningful area. Neither
  single-advisory endpoint declares envelope extraction, and the existing
  envelope/meta consistency tests cover them.
- `get_sigmet.time` is the recorded four-digit `HHMM` path component. Its new
  timestamp-name warning does not justify assigning a false date-time format.
  The other three authoring warnings are inherited.
- The omitted `atsu` and `end` query filters are disclosed in endpoint notes.
  The implementation report includes the `atsu` redirect and dated observations
  of `end` behaving unlike an upper bound. Path operations retain the unit/day
  queries. Combined unit/sequence filtering is not exposed by this request type.
  Those live experiments were not repeated in this review.
- `CwsuId` agrees with the captured OpenAPI enum. Sequence minimum 100 agrees
  with its request parameter schema; response sequences begin at 101. The
  schemas preserve nullable SIGMET fields and actual timestamp wire formats.
- No aviation endpoint is excluded, unverified, paginated or credentialed.
  No secret-shaped field was found in the new recordings. The standard secret
  checks pass. List recaptures may be empty in a quiet week; assertions then
  fail instead of claiming useful coverage.

## Manual standards and shape

| Rule | Review |
| --- | --- |
| S4 | Python manifest includes `py.typed`; no wheel was built in this review |
| S9 | Existing core maps 400 to `BadRequest`, 429 to `RateLimited`, and other failures to `ApiError`; aviation uses it unchanged |
| S10 | Existing transport uses the runtime `HttpClient`; no new transport implementation |
| S11 | Seven endpoint modules compose the aviation group; existing root composition remains unchanged |
| S12 | No discriminated request body in these GET operations |
| S17 | No dedicated Python type-usage file exists; the Python review must assess this inherited gap and aviation call coverage |
| S18, S24 | No new pagination; existing observation walker is outside this delta |
| S19, S23 | HTTP-only; recordings are replayed against the local mock in all three language suites |
| S27, S28 | Generated requests use the runtime date aliases and existing whole-request serializer; no new body serializer |

Read generated Python `list_sigmets`, TypeScript `get_sigmet`, Rust
`get_sigmet`, shared types, and router wiring. Dates retain their language
types; `HHMM` remains a string; advisory geometry and nullable properties are
visible in the return types. Full language approval is delegated to the three
language reviewers. The pre-existing package layout has not been certified as
meeting every target-shape clause by this endpoint review.

## Merge blockers

- The PR's observed GitHub checks are red (Python, TypeScript, Rust and
  recordings). Dependency pins must be made usable and verified; inherited
  failures remain failures.
- No successful `truewire/verify` status was confirmed. The status lookup was
  rate-limited, and the inspected verifier currently targets only the typed
  repository. A weather-gov verification lane is being added separately.
- Python, TypeScript and Rust review verdicts are pending. The Lead must rerun
  any affected acceptance checks and verify the final head before merging.

No implementation files were changed during this review.
