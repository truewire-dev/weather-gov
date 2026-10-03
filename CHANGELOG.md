# Unreleased

Regenerated Python, TypeScript, and Rust with Truewire revision
`62ed93389566d8bf540237a8204dd07fb69bfe46`. Shared schema references now retain
their public names and documentation. Recordings and wire JSON keys are unchanged.
Dependency pins are unchanged; this regeneration does not establish compatibility
with a newer runtime or waive the published-dependency checks.

## Rust migration

| Previous API | Regenerated API | Consumer change |
| --- | --- | --- |
| `OfficeHeadline.id2` | `OfficeHeadline.id` | Pass this headline token to `offices.get_headline`. The old URL field `id` is now `at_id` (wire `@id`). |
| `Zone.id2`, `Zone.id` | `Zone.id`, `Zone.at_id` | The natural `id` is the zone code; `at_id` is the URL. |
| `ZoneType2`, `Zone.type_2` | `ZoneKind`, `Zone.type_` | Use the shared zone-kind enum, also used by zone requests. |
| `ZoneType`, `Zone.type_` | `ZoneAtType`, `Zone.at_type` | These describe the separate JSON-LD `@type: "wx:Zone"`, not the zone kind. |
| `Transmitter.id`, `Transmitter.type_`, `TransmitterType` | `Transmitter.at_id`, `Transmitter.at_type`, `TransmitterAtType` | JSON-LD fields retain wire names `@id` and `@type`. |
| `ProductTypeCollection.graph`, `TransmitterCollection.graph` | `at_graph` on both collections | Access `@graph` through `at_graph`, including both radio and zone transmitter lists. |
| `TafCollection.graph`, `OfficeHeadlineCollection.graph` | `at_graph` on both collections | Wire key remains `@graph`. |
| `ZoneFeatureGeometry` | `ZoneGeometry = Option<ZoneGeometryValue>` | `ZoneFeature.geometry` uses the shared alias. Match `Some(ZoneGeometryValue::PolygonGeometry(...))` or `MultiPolygonGeometry(...)`; null is `None`. The field remains required. |
| `AlertFeatureGeometry` | `AlertGeometry = Option<AlertGeometryValue>` | `AlertFeature.geometry` is `Option<AlertGeometry>`: missing is `None`, explicit null is `Some(None)`, a polygon is `Some(Some(AlertGeometryValue::PolygonGeometry(...)))`. Preserve both layers. |
| Expanded coordinate tuples | `Position` | Point coordinates use `Position`; polygon and multipolygon coordinates use `Vec<Vec<Position>>` and `Vec<Vec<Vec<Position>>>`. |

Required nullable fields now reject a missing key while accepting explicit null.
Requests also provide generated `Request::new(...)` constructors for their required
fields. The headline lookup and serialization regression is in
`packages/rust/tests/probe_tru598.rs`; shared geometry and JSON-LD consumer checks
are in `packages/rust/tests/shared_types.rs`.

## Python and TypeScript

Consumers continue to use wire-keyed properties, including `['@id']`, `['@type']`,
and `['@graph']`. Shared geometry, `Position`, and `ZoneKind` names now appear in
field annotations instead of expanded copies. Do not rename payload keys to Rust
or Go member names. TypeScript retains the optional-request raw overload fix.

## Go rendering

This project has no configured Go package. For consumers rendering Go from this
spec, the same JSON-LD naming changes use `AtID`, `AtType`, and `AtGraph`.
`Graph -> AtGraph` applies to both product-type and transmitter collections, as
well as headline and TAF collections. The coordinate helper removals are:

| Removed helper | Shared replacement | Field type |
| --- | --- | --- |
| `PointGeometryCoordinates` | `Position` | `Position` |
| `PolygonGeometryCoordinatesItemItem` | `Position` | `[][]Position` |
| `MultiPolygonGeometryCoordinatesItemItemItem` | `Position` | `[][][]Position` |

The zone kind is the shared `ZoneKind` declared by this delivery schema. Historical
review snapshot `c0d49f01` had an inline zone kind and used `ZoneType`; examples for
that snapshot must not be copied here unchanged. This migration and the Rust
consumer tests adapt the bundle from typed commit
`8fc1f69d567439f98474098769c85402c631aa1d`.
