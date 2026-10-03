# TypeScript output review — TRU-995

Reviewed weather-gov PR #16 at **bbacd5055ee11bf8d715321ba63c2116cd0a97a0**,
base e548d4969ed176d87cb8654a47ff771db96c11ea. This evidence commit is separate
from the reviewed client. Generator: typed **62ed93389566d8bf540237a8204dd07fb69bfe46**
(Truewire 0.11.0 source). Confirmed its checkout and clean generator sources,
then reran generation against the assigned weather-gov worktree. No runtime
override, pin change, native build, merge, release, or publication was performed.

Environment: Node 24.21.0, Yarn 1.22.22, TypeScript 5.9.3, Vitest 4.1.11,
published **@truewire/core 0.1.1** from a fresh frozen-lockfile install.
Mock/generation use the merged generator wrapper at
`/home/truewire/work/scratch/TRU-997/from-TRU-609/toolchain/bin/truewire`.
It loads that revision's Python toolchain and core sources; it does not replace
the TypeScript runtime. The prior local TS core 0.2.0 results are diagnostic
handoff evidence only, not acceptance used by this review.

## Findings

| Severity | Where | What | Evidence | Suggested fix |
| --- | --- | --- | --- | --- |
| blocker | `packages/typescript/package.json`; `stations/get_observations.ts:2` | The committed dependency resolves core 0.1.1, which lacks the generated seek API. The package cannot typecheck or build; paged calls fail at runtime. Existing defect TRU-279 / published-dependency hold TRU-409, not caused by #184. | Fresh `yarn install --frozen-lockfile`; typecheck/build exit 2, missing SeekState/rowField/seek. Tests: 31 pass, 9 fail (eight seek calls and README compilation). See `logs/`. | Lead must resolve the existing published-runtime integration and obtain green exact-head checks. No pin changes are authorized in this review. |
| should | `offices/get_briefing.ts:70`; `offices/index.ts:38` | A widened `CallOptions` containing `validate: false` selects the validated overload. Both endpoint and router promise `TimestampIso` values although the recorded response returns strings. This is a residual overload defect, not a shared-reference regression or a claim that the literal radio fix failed. | `consumer.mts` compiles with strict tsc, then both calls throw `startTime.getTime is not a function`. `typing_widened.mts` fails with two TS2578 diagnostics. No client main import or seek dependency is involved. | Restrict the validated overload to options whose validate value is true/undefined, and provide an unknown-return fallback for widened/dynamic CallOptions in both endpoint and router generators. Keep literal-false and optional-request controls. |

The second defect is ordinary consumer code:

```ts
const options: CallOptions = { validate: false }
const result = await client.offices.getBriefing({ office_id: 'AKQ' }, options)
result.briefing!.startTime.getTime() // compiles; throws on the recorded string
```

After correction, the last line must be rejected because `result` can be raw JSON.
The reproduction obtains CallOptions through the public method's parameter type
so it can compile independently of the unrelated broken seek imports.
Lead owns defect routing under the current review brief; TRU-279 already tracks
the published-pin blocker. The new overload finding needs a generator follow-up.

## Checks

| Check | Result |
| --- | --- |
| merged-generator `truewire generate typescript --check` | exit 0, `Generated files match the plan for weather_gov (41 files).` |
| `yarn install --frozen-lockfile` | exit 0, core 0.1.1 |
| `yarn run typecheck` | exit 2, missing seek API |
| `yarn run build` | exit 2, missing seek API |
| `TRUEWIRE_BIN=<merged wrapper> nice -n 19 yarn run test --maxWorkers=1` | exit 1; 31 passed, 9 failed; all replay tests passed |
| required strict `typing_radio.ts` command below | exit 2, only missing seek exports and consequent implicit-any diagnostics; no TS2578 |
| `git ls-files reviews/TRU-597` | empty |
| `git diff --exit-code b90c998 HEAD -- spec packages/typescript/package.json packages/typescript/yarn.lock` before evidence commit | exit 0; nine operations, recordings and dependency pins unchanged |
| shared-source AST audit | 32 distinct shared structural declarations; Position, ZoneKind, AlertGeometry and ZoneGeometry each documented |
| `consumer.mts` strict compile | exit 0 |
| consumer runtime | shared alias / recorded geometry controls pass; widened-options calls reproduce two TypeErrors; exit 1 intentionally |
| `typing_widened.mts` | exit 2, two unused expected-error directives; after fixing the overload, this regression must exit 0 |

Required radio command (from repository root):

```sh
packages/typescript/node_modules/.bin/tsc --noEmit --strict --target ES2022 --module NodeNext --moduleResolution NodeNext --skipLibCheck packages/typescript/test/typing_radio.ts
```

The endpoint and router raw signatures both accept `Request | undefined` and
return `Promise<unknown>`. Required requests remain strict. Raw-undefined,
explicit-empty, validated-no-argument and required-request negative controls
are retained. The published dependency failure prevents claiming a green full
radio acceptance check; its six diagnostics are saved verbatim.

Reproduce the new defect after the frozen install:

```sh
# Set PAPERCLIP_RUN_SCRATCH_DIR to an existing ticket scratch directory outside a run.
bash reviews/TRU-995/run.sh
# Type regression: currently exit 2 / two TS2578s; must exit 0 after the fix.
packages/typescript/node_modules/.bin/tsc --noEmit --strict --target ES2022 --module NodeNext --moduleResolution NodeNext --skipLibCheck --typeRoots packages/typescript/node_modules/@types reviews/TRU-995/typing_widened.mts
```

## Source and wire audit

Read the complete TypeScript regeneration delta and all nine new endpoint modules,
their routers, shared types, transport, replay assertions and radio controls.
Read the migration bundle from typed 8fc1f69d567439f98474098769c85402c631aa1d
in the transferred TRU-609 evidence and compared the adapted CHANGELOG.md.
Final Zone.type uses shared ZoneKind; historical ZoneType examples were not substituted.
TypeScript wire properties remain `id`, `@id`, `@type`, and `@graph`.

Position appears directly at point coordinates and in polygon/multipolygon arrays;
ZoneFeature.geometry uses ZoneGeometry, AlertFeature.geometry uses optional
AlertGeometry. Codecs reuse those same named definitions. Their alias descriptions
are present, and field descriptions keep their own wording: PointGeometry.coordinates
is "Where the feature is", ZoneFeature.geometry is "The zone's outline; null in lists",
and AlertFeature.geometry is "The area covered, when it was drawn as a polygon".
No duplicate shared structural declarations or missing alias docs were found.

Read five wire responses directly: KSEA exact observation, KSEA station, active
office briefing, Wakefield headline collection, and Seattle transmitter. The
timestamp/string distinction, nullable summary, decimal-string frequency and
JSON-LD identifiers agree with the generated validated types and codecs.
The consumer additionally parses recorded zone and alert geometries through the
public aliases, with nullable and optional TypeScript assignments checked.

This is the requested bounded TypeScript review, not a repeat of upstream
generator approval or other-language verification. The handoff's red
published-dependency verifier remains a delivery hold.

**CHANGES REQUESTED**
