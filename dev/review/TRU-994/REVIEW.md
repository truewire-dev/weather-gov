# Python review of weather-gov #16

Reviewed client **bbacd5055ee11bf8d715321ba63c2116cd0a97a0**, base
`e548d4969ed176d87cb8654a47ff771db96c11ea`, on 2026-10-03.
Regeneration baseline is `b90c998de0ebfaaa7c14fa25b75ac3dc1706a4b6`, including
the TypeScript overload integration. The Python output matches merged generator
**62ed93389566d8bf540237a8204dd07fb69bfe46**. No new defect was demonstrated in
the regenerated Python aliases or descriptions. The delivery gates below remain red.

| Severity | Where | What | Evidence | Suggested fix |
| --- | --- | --- | --- | --- |
| blocker | `packages/python/pyproject.toml:26`, consumed by `.github/workflows/ci.yml` | The declared development toolchain cannot load this client's seek schema, so a fresh supported installation cannot run the required checks or collect the replay tests. This predates the regeneration and remains unresolved at this head. | Fresh install resolves `truewire==0.10.0`, core `0.2.1`. `env -u PYTHONPATH .venv/bin/truewire check` exits 1 with eight seek-schema validation errors; `env -u PYTHONPATH .venv/bin/python -m pytest packages/python/test -q -rs` exits 2 with two collection errors. Missing cursor `parameter`/`from` and rejected `field`/`unique`/`bound`/`anchor`/`rows` identify the schema-version mismatch. | Lead must route an authorized toolchain compatibility solution and rerun published-dependency CI. No dependency pin change is authorized by this review. |
| should | `.agents/rules/` | Required language rules are absent, so the standards gate fails even with the corrected generator. This also predates the regeneration. | With the merged generator, `truewire standards` exits 1: 15/16 checks pass; `python.md`, `typescript.md`, and `rust.md` are missing. The directory contains only `.gitkeep`. | Lead should route vendoring the correct rule files, preserving deliberate local instructions, then rerun `truewire standards`. |

The task-specific direction says to list defects here and let the Lead route fixes;
this review creates no duplicate remediation issues and changes no dependency pins.

## Verification

New independent runs used CPython **3.11.16**, published **truewire-core 0.2.1**,
Pydantic **2.13.5**, and pyright **1.1.414**. The environment was installed using
`uv pip install --python .venv/bin/python -e 'packages/python[dev]'`.
For corrected-generator checks only, `PYTHONPATH` named the exact merged
checkout's `packages/truewire/src`. It did **not** include `packages/core-python/src`;
the runtime imported from this review workspace's `.venv/site-packages`.
Installed toolchain distribution metadata still says 0.10.0 when source is overlaid;
the actual generator source revision is the Git hash above.

| Check | Result |
| --- | --- |
| Corrected `truewire generate python --check` | Exit 0: `Generated files match the plan for weather_gov (39 files).` |
| Corrected `truewire generate python`, then diff Python output and manifest | Exit 0, no diff |
| Corrected `python -m pytest packages/python/test -q -rs` with published core | Exit 0: `142 passed in 50.40s` |
| `pyright --project packages/python/pyrightconfig.json` | Exit 0: zero errors/warnings/information |
| `consumer.py`, runtime | Exit 0: aliases, geometry missing/null/value, real mock headline lookup, radio typed/raw calls |
| `pyright --pythonpath .venv/bin/python dev/review/TRU-994/consumer.py` | Exit 0: zero errors/warnings/information |
| `source_check.py` | Exit 0: alias names, field description precedence, alias declaration docs |
| Corrected `truewire check` | Exit 0: 28 endpoints, 31 recordings, no errors, three existing authoring warnings |
| Corrected `truewire examples --require-verified` | Exit 0: 28/28 paired, 31 request/response pairs |
| Corrected `truewire surface` | Exit 0: 28 generated callables for 28 specs |
| Corrected `truewire docs check` / `docs lint` | Exit 0: 12 blocks across four pages / OK |
| Package Ruff check / format check | Exit 0 / exit 0 |
| Published toolchain checks and corrected standards | Fail as recorded above; no waiver |
| Exact-head `truewire/verify` read from GitHub | `failure`: 5/5 gates failed against base `e548d496` |

No Rust/native builds were started, and no shared locks were acquired. TS/Rust
diagnostic runtime overrides from the implementation handoff are not Python
approval evidence and do not establish published dependency compatibility.

## Source and consumer audit

Read all of `schemas.py`, the regeneration diff, request documentation, the core
validation/transport path, and recording/replay tests. Read the historical consumer
bundle at typed `8fc1f69d567439f98474098769c85402c631aa1d` and its delivered migration
in `CHANGELOG.md`. The delivered schema uses **ZoneKind**, not historical ZoneType.
Python continues to use `id`, `@id`, `@type`, and `@graph` as distinct wire keys.
No public Python shared declaration disappeared in this regeneration.

`Zone.type` now names `ZoneKind`; `ZoneFeature.geometry` names required nullable
`ZoneGeometry`; `AlertFeature.geometry` names `NotRequired[AlertGeometry]`.
Coordinates retain `Position` through all nested array levels. The consumer program
checks valid polygon values, nulls, rejection of omitted required zone geometry,
and preservation of omitted optional alert geometry using the published runtime.
It passes a listed headline's natural `id` into the actual mock-backed detail call.

Source assertions check field-specific descriptions against the spec and separate
declaration descriptions on all four shared aliases. All direct field references
in this client carry descriptions, so a missing-field-description fallback is not
exercised here. The only description-free reference is the ZoneKind array item in
`zones.list_zones`, which retains the alias and its declaration documentation.
The shared dependency graph is acyclic: there are no recursive aliases in this
delivery. This review does not claim recursive runtime coverage or rerun the
already-approved generator's synthetic regression suite.

Recordings inspected include station KSEA, the Wakefield headline, active briefing,
Seattle zone, and the individual alert; the suite replays all 31 recordings.
Dates remain formatted timestamp types, radio frequency remains Decimal, and
coordinates normalize to the declared tuples. The nine added operations, all
recordings, and dependency manifests/lockfiles are byte-identical to `b90c998`.

To rerun the consumer checks, set `PYTHONPATH` to
`<checkout-at-62ed93389>/packages/truewire/src`, then run the two adjacent programs
and the pyright command above. For the pinned-toolchain failure, explicitly unset
`PYTHONPATH` as shown in the findings table. Diagnostic green results do not replace
the failing declared setup.

No merge, release, or publication. Lead owns routing and the multi-language merge.

**CHANGES REQUESTED**
