# TypeScript review: weather-gov #16

**Changes requested** for head `6e19e9dd5850a8655d5eeed010a5ca22fd086b09`, against
`agent/TRU-5` (`e548d4969ed176d87cb8654a47ff771db96c11ea`). Review scope: all nine added
operations, changed shared types, their recordings, and TypeScript replay assertions.

| Severity | Where | What | Evidence | Suggested fix |
| --- | --- | --- | --- | --- |
| should | `packages/typescript/src/weather-gov/radio/index.ts:35`; `radio/list_transmitters.ts:21` | New radio operation repeats the optional-request raw-overload defect tracked by TRU-572. `listTransmitters(undefined, { validate: false })` selects the validated return type. | `optional-request.ts` exits 2 with TS2578 on lines 9 and 15: typed field access on unvalidated data unexpectedly compiles. `{}` returns unknown correctly. Changing only both raw signatures to `Request \| undefined` in scratch makes the same regression exit 0. | Regenerate with the optional-request fix from typed #80, `3920497150b004478e1e7160d4a34a28c720cac0`, or its merged successor. Apply it to both endpoint and router. |
| blocker, existing base | `packages/typescript/package.json:57`; `stations/get_observations.ts:2` | Published runtime 0.1.1 lacks seek exports already used on the base. This is separate from the new radio defect. | Typecheck against the actual npm tarball fails with TS2305 for `SeekState`, `rowField`, and `seek`, plus consequent TS7006 errors. The chained test command does not run. These imports are unchanged by #16. | Resolve the existing runtime-release/pin delivery tracked by TRU-409; no pin changes made in this review. |
| should, already tracked | `packages/rust/src/weather_gov/types/mod.rs:98-102` | `OfficeHeadline.id` means wire `@id` (URL); `id2` means wire `id` (headline token). TypeScript keeps both names correctly. | Before: passing `headline.id` to `get_headline` sends the URL, while TS passes `headline.id` as the token. After deterministic naming: `headline.at_id` is the URL and `headline.id` is the token. Rust replay lines 802-805 and 832 explicitly accommodate `id2`, so passing replay does not resolve the API naming defect. | Existing TRU-534 owns the generator naming fix; regenerate after it. No duplicate generator ticket or Rust build in this TS review. |

## Verification

Toolchain: archive of fetched typed `origin/truewire`,
`c1d4c279faf6bbe12c4857a3961335e1f812f001`; CLI `truewire 0.11.0`,
Python runtime `truewire-core 0.3.0`. Installed in run-owned scratch with:

```sh
uv venv "$PAPERCLIP_RUN_SCRATCH_DIR/venv"
uv pip install --python "$PAPERCLIP_RUN_SCRATCH_DIR/venv/bin/python" \
  -e "$PAPERCLIP_RUN_SCRATCH_DIR/typed/packages/core-python" \
  -e "$PAPERCLIP_RUN_SCRATCH_DIR/typed/packages/truewire"
```

The commands below ran from the reviewed repository using that CLI:

| Command | Result |
| --- | --- |
| `truewire generate typescript --check` | `Generated files match the plan for weather_gov (40 files).` |
| `truewire check` | `Result: OK`; 28 endpoints, 31 examples, zero errors; three pre-existing authoring warnings. |
| `truewire examples --require-verified` | Exit 0; 28/28 paired coverage, 31 requests and responses, all 200. |
| `truewire standards` | `All mechanically-enforced checks pass.` |
| `truewire surface` | `Callables: 28 generated, 0 hand-written, 0 declared absent, over 28 spec(s)` |
| `truewire docs check` | 12 blocks across four pages: OK. |
| `truewire docs lint` | `Docs lint: weather_gov: OK` |

The initial assigned-worktree `yarn run typecheck && yarn run test` passed typecheck,
then failed setup because `.venv/bin/truewire` was absent. With `TRUEWIRE_BIN` set to
the scratch CLI, all 40 tests passed. That preinstalled `@truewire/core` identified
itself as 0.1.1 but differed from the actual npm tarball, including seek exports;
it cannot establish published-dependency compatibility.

Published dependency check: fetched the immutable `@truewire/core@0.1.1` tarball via
`npm pack @truewire/core@0.1.1`, extracted it in scratch, and pointed a scratch copy's
`node_modules/@truewire/core` at it. `yarn run typecheck && yarn run test` fails as
reported above. Source, package pins, and locks were unchanged.

Controlled local diagnostic: built `packages/core-ts` at the exact toolchain SHA above
using `npm install --ignore-scripts --no-audit --no-fund` and `npm run build`.
Its version is **0.2.0**. A pristine archive of the reviewed client head used that
runtime through a scratch-only `node_modules/@truewire/core` symlink. Commands:

```sh
# In the scratch client's packages/typescript:
TRUEWIRE_BIN="$PAPERCLIP_RUN_SCRATCH_DIR/venv/bin/truewire" yarn run typecheck
TRUEWIRE_BIN="$PAPERCLIP_RUN_SCRATCH_DIR/venv/bin/truewire" yarn run test --maxWorkers=1
yarn run build
```

All passed: three test files, 40 tests. Builds were sequential; test workers capped
at one. This is diagnostic validation with a local runtime, **not a green published
dependency check**. Node 24.21.0, TypeScript 5.9.3, Vitest 4.1.11, Yarn 1.22.22.

## Reproductions

From repository root, with a seek-capable runtime installed:

```sh
packages/typescript/node_modules/.bin/tsc --noEmit --strict --target ES2022 \
  --module NodeNext --moduleResolution NodeNext --skipLibCheck \
  reviews/TRU-597/optional-request.ts
```

Expected on the reviewed head: exit 2 with exactly two TS2578 diagnostics (lines 9,
15). Expected after correction: exit 0. Confirmed both results using runtime 0.2.0;
the correction was made only in the disposable diagnostic copy, after its normal
suite and build passed.

The additional user program uses real recorded payloads and an injected fetch to
check exact outgoing paths, without live network calls:

```sh
node reviews/TRU-597/wire-probe.mjs /path/to/built/weather-gov
```

Result: `PASS: nine operations, eleven calls; exact Date path, nulls, distinct IDs,
and decimal strings preserved`.

It covers station geometry; observation Date serialized as
`/stations/KSEA/observations/2026-09-30T16:53:00Z`; TAF Date fields; active and null
briefing; null headline summary and both IDs; weather-story Date fields; frequency
`162.550` preserved exactly; every last-page radio frequency, all 228 rows, absent
pagination, and raw response passthrough. The last-page payload is deliberately
injected for the optional-request call; this probe does not claim the live first
page equals that recording. The repository replay test uses its recorded cursor.

Read all ten response recordings for the nine operations, plus the existing county
transmitter recording and shared-schema changes. No additional wire-shape defect
found. Radio pagination is intentionally manual: the spec documents that the next
cursor is embedded in a URL, and the generated method declares no automatic walk.
The assertions cover every added operation; none exercises the raw omitted-request
overload, hence the separate type regression.

**Changes requested.**
