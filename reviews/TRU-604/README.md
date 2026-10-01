# Aviation TypeScript review reproduction

PR #17 implementation `29bc3513d2a3b915ad36dfae99de0bf11680b6b5`; reviewed final head `afe2e7ca3e445ac463d0ca842e8cec0a4b5b3315` adds only REVIEW.md.

The generated optional-request raw overload drops `undefined`. Both the leaf and router incorrectly return SigmetCollection for `listSigmets(undefined, { validate: false })`. The timestamp on the wire is a string, so the advertised Date operation throws. This is the aviation manifestation of existing TRU-572; the Lead owns downstream regeneration after that fix.

Use Node and package dependencies from packages/typescript, with a built @truewire/core from typed c1d4c279 (0.2.0). The committed 0.1.1 dependency independently cannot compile the inherited observation walker; do not interpret a source-runtime run as a clean-pin pass. The test directory needs dependency resolution to the same installation, e.g. a repository-root node_modules symlink to packages/typescript/node_modules.

From the repository root:

```sh
node node_modules/typescript/bin/tsc --noEmit --strict --target ES2022 --module NodeNext --moduleResolution NodeNext --skipLibCheck reviews/TRU-604/optional-request.ts
node node_modules/vitest/vitest.mjs run --config reviews/TRU-604/vitest.config.ts --reporter=verbose
```

The first command exits 2 before the fix, with TS2578 at lines 9 and 19: Date access is unexpectedly accepted. The explicit-empty raw and validated controls work. After regeneration it must exit 0. The runtime probe passes three assertions at this head: it demonstrates the TypeError, checks tuple/null/feature fidelity, and verifies date/HHMM/filter serialization. After fixing the type overload, remove or narrow the intentionally unsafe Date access in the runtime demonstration if adding it to a package typecheck.

Do not copy the entire review directory to a product branch. Move only the useful compile regression into the package test inputs if the Lead requests it.
