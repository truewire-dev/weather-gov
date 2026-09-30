# weather-gov

A typed client for the US National Weather Service API (`api.weather.gov`), built with
[Truewire](https://truewire.dev). This file is the entrypoint an agent reads; `CLAUDE.md`
points here.

## Layout

- `spec/`: the specification. One `endpoint.json` per endpoint, recordings in `examples/`
  beside it. The spec is the product; everything else is rendered from it or describes it.
- `packages/`: one package per language, each generated from the spec over a hand-written core.
- `docs/`: the documentation site. `docs.yml` is its nav and quickstart.
- `dev/capture/`: how each recording was produced; never a credential. Empty here:
  `packages/python/test/recapture.sh` re-records every example.
- `.agents/skills/`, `.agents/rules/`: the skills to follow and the rules per language.
  `.claude/skills` and `.claude/rules` are symlinks to them.
- `truewire.toml`: the one project file.

## Credentials

None. The National Weather Service answers every endpoint here to any caller that names
itself in `User-Agent`, which the core sends. `truewire.toml` declares no `[secrets]`.

## Gates

Run these from the repository root before pushing. CI (`.github/workflows/ci.yml`) runs the
block below in its `gates` job, except `examples`, which runs in `recordings`.

```
truewire check
truewire standards
truewire generate python --check
truewire generate typescript --check
truewire generate rust --check
truewire docs check
truewire docs lint
truewire examples --require-verified
```

`gates` also regenerates each language and fails on any `git diff` in `packages` or
`.truewire`, and runs the Python package's tests, types and lint, with these arguments:

```
pytest packages/python/test -q -rs
pyright --project packages/python/pyrightconfig.json
ruff check --config packages/python/ruff.toml packages/python/src packages/python/test
ruff format --check --config packages/python/ruff.toml packages/python/src packages/python/test
```

The `typescript` job runs `yarn run typecheck` and `yarn run test` in `packages/typescript`.
The `rust` job runs `cargo build` and `cargo test` in `packages/rust` with `RUSTFLAGS='-D warnings'`, so a warning fails it.
