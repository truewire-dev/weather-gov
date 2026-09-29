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

Run these before pushing. CI (`.github/workflows/ci.yml`) runs them in its `gates` and
`recordings` jobs, and each package's tests in the others.

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

CI also regenerates each language and fails on any `git diff` in `packages` or `.truewire`.
Also: `pytest packages/python/test`; `pyright` and `ruff check` / `ruff format --check` with
`--config packages/python/ruff.toml`; `yarn run typecheck` in `packages/typescript`;
`cargo build` in `packages/rust`.
