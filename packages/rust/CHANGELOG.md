# Changelog

## 0.3.0 (unreleased)

- **Breaking: `Weather` gains public `glossary`, `radar`, `radio` and `zones` fields.**
  Struct literals must initialize all four; exhaustive destructuring must name them or
  include `..`.
  Prefer `Weather::new` or `Weather::with_options` for construction.
- **Breaking: the unreleased glossary response is now `GlossaryResponse`.** Import it
  from `weather_gov::glossary::list_terms::GlossaryResponse`; `glossary::Glossary`
  remains the endpoint group. Python and TypeScript use the same response rename.
- **Alert nullability:** `Alert.description` is now `Option<String>` but remains
  required on the wire. `Alert.response` is `Option<Option<AlertResponse>>`, preserving
  omission versus explicit null and validating non-null CAP action values.
- **Fixed: a list filter with more than one value kept only the last.** The service reads
  `id=KSEA,KPDX` and keeps only the last of `id=KSEA&id=KPDX`, and the client sent the
  second form, so `stations.list_stations` given the ids `KSEA` and `KPDX` answered with
  KPDX alone. Every list filter now travels as one comma-separated item:
  `alerts.get_active_alerts`, `stations.list_stations`, `zones.list_zones` and
  `zones.list_zones_by_type`.
- **`stations.get_observations_paged` walks a whole span of observations.** The endpoint
  declares `seek` pagination anchored to `end` (ADR 0013): a full page moves `end` back to
  the oldest observation it held and asks again, never past your own `start`. It takes a
  `stations::get_observations::GetObservationsPagedRequest` (the same `Request`) and returns
  a `PaginatedResponse`. Await it for every observation newest first, or walk `rows()` (or
  `pages()`, which also carries each page's state) one page at a time. Both are a
  `futures::Stream`, so `.next()` needs `futures::StreamExt` in scope. 0.2.0 had no paged
  method, so `get_observations` returned only the newest 500.
- **`Weather::RATE` and `Weather::RETRY`** state the client's `[policy]`: the requests per
  second the core's `HttpClient` paces to, and whether it retries on its own. `truewire.toml`
  declares no `[policy]`, so they are `None` and `false`.
- **Breaking: ten types moved to `weather_gov::types`.** `ObservationCollection`,
  `StationCollection`, `AlertCollection` and `ProductTypeCollection` are each returned by
  more than one endpoint now, so they are shared schemas. Import them, and the types they
  carry, from
  `weather_gov::types`:
  - `stations::get_observations::ObservationCollection`
  - `stations::get_observations::ObservationCollectionType`
  - `stations::get_observations::ObservationPagination`
  - `stations::list_stations::StationCollection`
  - `stations::list_stations::StationCollectionType`
  - `stations::list_stations::CollectionPagination`
  - `alerts::get_active_alerts::AlertCollection`
  - `alerts::get_active_alerts::AlertCollectionType`
  - `products::list_product_types::ProductTypeCollection`
  - `products::list_product_types::ProductType`

  The old paths fail to compile (`E0432`, or `E0603` for the three the modules still
  import privately).
- **Breaking: `types::AlertCollection` gains `pagination`.** It is
  `Option<types::AlertPagination>`, and only `alerts.list_alerts` sends it. An
  `AlertCollection { .. }` literal must now name it.
- **Breaking: `types::Station` gains `distance` and `bearing`.** Both are
  `Option<QuantitativeValue>` and only `stations.list_stations_for_gridpoint` sends them.
  A `Station { .. }` literal must now name both, or end in `..Default::default()`.
- **Eight more endpoints: the rest of the text products API.** `products::list_products`
  (a span, filtered by type, office, location or WMO heading), `products::get_product`,
  `products::list_products_by_type`, `products::list_products_by_type_and_location`,
  `products::get_latest_product`, `products::list_locations`,
  `products::list_locations_for_type` and `products::list_types_for_location`. The service
  sends an empty location map as `[]` (most type codes in `list_locations_for_type`); the
  core turns it into an empty `HashMap`. `get_latest_product` answers HTTP 500, not 404,
  where the location has issued nothing of that type.
- **Breaking: `meta::DefaultMeta` gains `empty_map`.** It is the `meta` every generated
  call passes its core, and an `Option<String>` naming the field to read `[]` as an empty
  map. A `DefaultMeta { .. }` literal must now name it.
- **Eight more endpoints: zones, and the stations of a zone or grid cell.** A new `zones`
  group (`list_zones`, `list_zones_by_type`, `get_zone`, `get_forecast` and
  `list_transmitters`), and `stations.list_stations_for_zone`,
  `stations.list_stations_for_gridpoint` and `stations.get_observations_for_zone`. Their
  requests take a zone type as one shared enum, `types::ZoneKind`.
- **Seven more endpoints: aviation weather.** A new `aviation` group: `get_cwsu`,
  `list_cwas` and `get_cwa` for the Center Weather Service Units and their advisories, and
  `list_sigmets`, `list_sigmets_for_atsu`, `list_sigmets_for_atsu_on_date` and
  `get_sigmet` for SIGMETs and AIRMETs. Their outlines are a `types::AdvisoryPolygon`, whose
  positions are latitude first, unlike every other geometry in this API.
  A unit is named by the shared enum `types::CwsuId`.
- **Seven more endpoints: the rest of the alerts API, and the glossary.**
  `alerts.list_alerts` (the last week, in effect or not, by `cursor`),
  `alerts.count_active_alerts`, `alerts.get_active_alerts_for_zone`, `_for_area` and
  `_for_region`, `alerts.list_alert_types`, and a new `glossary` group with `list_terms`.
- **Nine more endpoints: one station, one observation, TAFs, office news, and radio.**
  `stations.get_station`, `stations.get_observation` (the observation at an exact
  timestamp) and `stations.list_tafs`; `offices.get_briefing`, `offices.list_headlines`,
  `offices.get_headline` and `offices.list_weather_stories`; and a new `radio` group,
  `list_transmitters` and `get_transmitter`. `types::OfficeHeadline.id2` is the headline
  token passed to `offices.get_headline`; `types::OfficeHeadline.id` is its URL
  (wire `@id`). `types::Zone.id2` is the zone code; `types::Zone.id` is its URL
  (wire `@id`). The [Rust names](../../CHANGELOG.md#rust-names) table lists every
  JSON-LD field name truewire 0.11 derives.
- **`Transmitter` and `TransmitterCollection` are in `weather_gov::types`**, not
  `zones::list_transmitters`, since the `radio` endpoints return them too.
  `TransmitterCollection` gains `pagination: Option<CollectionPagination>`, which only
  `radio.list_transmitters` sends.
- **Eight more endpoints: a new `radar` group.** `list_stations`, `get_station` and
  `list_station_alarms` for the radars themselves; `list_servers`, `get_server`, `get_queue`
  and `list_spgds` for the network that distributes their data; and `get_profiler`, which
  has no recording: every profiler answered 404 on 2026-10-01, so it returns
  `serde_json::Value`. `get_queue` and `list_spgds` take an ISO 8601 interval as a
  `String`, `get_queue`'s `created` included. The SPG reports' Unix seconds sent
  as strings are `TimestampSecondsString`, which needs the truewire-core this crate is
  generated against, not crates.io 0.1. `get_queue`'s `host` is one shared enum,
  `types::RadarHost`, in the request and on every product, so `product.host == request.host`
  compiles; unreleased main had two, `get_queue::RequestHost` and
  `get_queue::RadarQueueProductHost`. `radar::get_queue::Request` requires its `host`, so it
  has no `Default`: name every field.
