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
- **Breaking: six types moved to `weather_gov::types`.** `ObservationCollection` and
  `StationCollection` are each returned by more than one endpoint now, so they are shared
  schemas. Import them, and the types they carry, from `weather_gov::types`:
  - `stations::get_observations::ObservationCollection`
  - `stations::get_observations::ObservationCollectionType`
  - `stations::get_observations::ObservationPagination`
  - `stations::list_stations::StationCollection`
  - `stations::list_stations::StationCollectionType`
  - `stations::list_stations::CollectionPagination`

  The old paths fail to compile (`E0432`, or `E0603` for the two the modules still import
  privately).
- **Breaking: `types::Station` gains `distance` and `bearing`.** Both are
  `Option<QuantitativeValue>` and only `stations.list_stations_for_gridpoint` sends them.
  A `Station { .. }` literal must now name both, or end in `..Default::default()`.
- **Eight more endpoints: zones, and the stations of a zone or grid cell.** A new `zones`
  group (`list_zones`, `list_zones_by_type`, `get_zone`, `get_forecast` and
  `list_transmitters`), and `stations.list_stations_for_zone`,
  `stations.list_stations_for_gridpoint` and `stations.get_observations_for_zone`. Their
  requests take a zone type as one shared enum, `types::ZoneKind`.
- **Nine more endpoints: one station, one observation, TAFs, office news, and radio.**
  `stations.get_station`, `stations.get_observation` (the observation at an exact
  timestamp) and `stations.list_tafs`; `offices.get_briefing`, `offices.list_headlines`,
  `offices.get_headline` and `offices.list_weather_stories`; and a new `radio` group,
  `list_transmitters` and `get_transmitter`. `types::OfficeHeadline.id` is the headline
  token passed to `offices.get_headline`; `types::OfficeHeadline.at_id` is its URL
  (wire `@id`). `types::Zone.id` is the zone code; `types::Zone.at_id` is its URL
  (wire `@id`).
- **Rust migration:** see the [complete Rust migration](../../CHANGELOG.md#rust-migration)
  for previous-to-current API comparisons, including JSON-LD field names, shared types,
  geometry aliases, required nullable fields, and request constructors.
- **`Transmitter` and `TransmitterCollection` are in `weather_gov::types`**, not
  `zones::list_transmitters`, since the `radio` endpoints return them too.
  `TransmitterCollection` gains `pagination: Option<CollectionPagination>`, which only
  `radio.list_transmitters` sends.
