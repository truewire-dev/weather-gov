# Unreleased

Regenerated Python, TypeScript, and Rust with the published `truewire==0.11.0`, the
version the dependency pins name. Recordings and wire JSON keys are unchanged.

## Rust names

Rust field names for the JSON-LD keys are the ones 0.11 derives:

| Wire key | Rust field |
| --- | --- |
| `@id` on `OfficeHeadline`, `Zone`, `Transmitter` | `id` (the URL) |
| `id` on `OfficeHeadline`, `Zone` | `id2`: pass `OfficeHeadline.id2` to `offices.get_headline` |
| `type` on `Zone` | `type_2: ZoneType2`, the zone kind |
| `@type` on `Zone`, `Transmitter` | `type_` |
| `@graph` on the product-type, transmitter, headline and TAF collections | `graph` |

`ZoneFeature.geometry` is `Option<ZoneFeatureGeometry>` and `AlertFeature.geometry` is
`Option<Option<AlertFeatureGeometry>>`: missing is `None`, explicit null is `Some(None)`.
Required nullable fields such as `ZoneFeature.geometry` still accept a missing key (TRU-760).
Stable JSON-LD names (`at_id`, `at_graph`), shared geometry types and request
constructors need a newer toolchain release; they and their tests return then (TRU-1046).
`packages/rust/tests/probe_tru598.rs` and `packages/rust/tests/shared_types.rs` check
the headline lookup and the wire round trips under the 0.11 names.

## Python and TypeScript

Consumers use wire-keyed properties, including `['@id']`, `['@type']` and `['@graph']`.
`Position` and `ZoneKind` are exported from the shared schemas.
