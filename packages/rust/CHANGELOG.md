# Changelog

## 0.3.0 (unreleased)

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
- **Breaking: eight types moved to `weather_gov::types`.** `ObservationCollection`,
  `StationCollection` and `ProductTypeCollection` are each returned by more than one
  endpoint now, so they are shared schemas. Import them, and the types they carry, from
  `weather_gov::types`:
  - `stations::get_observations::ObservationCollection`
  - `stations::get_observations::ObservationCollectionType`
  - `stations::get_observations::ObservationPagination`
  - `stations::list_stations::StationCollection`
  - `stations::list_stations::StationCollectionType`
  - `stations::list_stations::CollectionPagination`
  - `products::list_product_types::ProductTypeCollection`
  - `products::list_product_types::ProductType`

  The old paths fail to compile (`E0432`, or `E0603` for the three the modules still
  import privately).
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
