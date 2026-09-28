# TRU-31 review harness: `getObservationsPaged`

Drives the generated TypeScript seek walk against a fake service built from the recorded
76 KSEA rows (`ksea_window`), no mock and no network. Needs `@truewire/core` with `seek`
(typed-port), as in TRU-31's setup:

    sed -i 's#"@truewire/core": "^0.1.1"#"@truewire/core": "file:../../../tc/packages/core-ts"#' package.json
    yarn install && npx vitest run --config review/vitest.config.ts --reporter verbose

Expected on PR head 9e8d082: `limit 1 ... walks all 76 rows` FAILS with a LogicError;
the others pass and log what `limit` 600/0/2.5 and a JSON-saved `page.next` do.
