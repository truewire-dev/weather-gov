# TRU-1044 reproductions (TypeScript review of #15, #13, #18, #20)

Build the TS package at the PR head (merged with #15 for #13/#18/#20), then run from the repo root:

- `node review/TRU-1044/locations_empty.mjs`: #13 blocker, exits 1 while
  `products.listLocationsForType` throws `ValidationError: expected object, got array at /locations`.
- `live15.mjs`, `live13.mjs`, `live20.mjs`: the live validated sweeps the verdicts quote
  (two-value list filters, every products endpoint, every radar station, profilers).
