# Changelog

## 0.3.0 (unreleased)

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
  `StationCollection` and `AlertCollection` are each returned by more than one endpoint
  now, so they are shared schemas. Import them, and the types they carry, from
  `weather_gov::types`:
  - `stations::get_observations::ObservationCollection`
  - `stations::get_observations::ObservationCollectionType`
  - `stations::get_observations::ObservationPagination`
  - `stations::list_stations::StationCollection`
  - `stations::list_stations::StationCollectionType`
  - `stations::list_stations::CollectionPagination`
  - `alerts::get_active_alerts::AlertCollection`
  - `alerts::get_active_alerts::AlertCollectionType`

  The old paths fail to compile (`E0432`, or `E0603` for the three the modules still
  import privately).
- **Breaking: `types::AlertCollection` gains `pagination`.** It is
  `Option<types::AlertPagination>`, and only `alerts.list_alerts` sends it. An
  `AlertCollection { .. }` literal must now name it.
- **Breaking: `types::Station` gains `distance` and `bearing`.** Both are
  `Option<QuantitativeValue>` and only `stations.list_stations_for_gridpoint` sends them.
  A `Station { .. }` literal must now name both, or end in `..Default::default()`.
- **Eight more endpoints: zones, and the stations of a zone or grid cell.** A new `zones`
  group (`list_zones`, `list_zones_by_type`, `get_zone`, `get_forecast` and
  `list_transmitters`), and `stations.list_stations_for_zone`,
  `stations.list_stations_for_gridpoint` and `stations.get_observations_for_zone`. Their
  requests take a zone type as one shared enum, `types::ZoneKind`.
- **Seven more endpoints: the rest of the alerts API, and the glossary.**
  `alerts.list_alerts` (the last week, in effect or not, by `cursor`),
  `alerts.count_active_alerts`, `alerts.get_active_alerts_for_zone`, `_for_area` and
  `_for_region`, `alerts.list_alert_types`, and a new `glossary` group with `list_terms`.
