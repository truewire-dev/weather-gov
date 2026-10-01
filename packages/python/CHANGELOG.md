# Changelog

## Unreleased

Generated with truewire 0.11.

- **Breaking: `stations.get_observations_paged` walks the whole span.** The endpoint
  declares `seek` pagination anchored to `end` instead of `window` (ADR 0013). A full page
  now moves `end` back to the oldest observation it held and asks again, where it used to
  raise. The method returns a `PaginatedResponse`: await it for every observation newest
  first, or iterate it for one page (a list of observations, no longer the whole
  `ObservationCollection`) at a time. `max_pages` and `allow_truncation` are gone.
- **`start` and `end` are optional on the walk.** Leaving either out used to raise
  `ValueError`; now a walk without `end` starts from the newest observation, and one
  without `start` goes back as far as the service keeps.
- **Eight more endpoints: zones, and the stations of a zone or grid cell.** A new `zones`
  group (`list_zones`, `list_zones_by_type`, `get_zone`, `get_forecast` and
  `list_transmitters`), and `stations.list_stations_for_zone`,
  `stations.list_stations_for_gridpoint` and `stations.get_observations_for_zone`.
- **`ObservationCollection` and `StationCollection` are shared schemas.** Each is returned
  by more than one endpoint now, so they moved from `weather_gov.stations.get_observations`
  and `weather_gov.stations.list_stations` to `weather_gov.schemas`, with
  `ObservationPagination` and `CollectionPagination`. The old paths still import at
  runtime, but type checkers flag them (pyright reports `reportPrivateImportUsage`), so
  import all four from `weather_gov.schemas`. `Station` gains optional `distance` and
  `bearing`, which only `stations.list_stations_for_gridpoint` sends.
- **`Weather.new(proxy=...)`**: an HTTP(S) proxy URL every call goes through, for a caller
  that cannot set the process environment. Left out, `HTTPS_PROXY`/`HTTP_PROXY` (and
  `NO_PROXY`) from the environment are still used; a proxy given here ignores them.
  Needs `truewire-core>=0.3.0`, the first release whose `HttpClient` takes `proxy=`.

## 0.1.0

First release.

- **Eleven endpoints across six groups**, none of which need credentials: the grid a
  coordinate falls in, the twice-daily and hourly forecasts, the raw gridded data behind
  both, observation stations and what they have reported, and every alert in effect.
- **Three response vocabularies**, described as they actually arrive: GeoJSON for most of
  it, schema.org for the offices, JSON-LD for the product types.
- **Every measurement carries its unit.** A temperature is a `QuantitativeValue` with a
  WMO unit code and a nullable value, because that is what the service sends and the null
  is common rather than exceptional.
- **`window` pagination on station observations**, with the truncation guard that makes it
  safe: the service caps a response at 500 observations and says nothing about the ones it
  withheld, so a full page raises rather than letting the walk step past them.
- All eleven endpoints carry recorded request/response pairs captured from the live API
  through this same client, replayed by the test suite against a local mock. No endpoint
  has an excuse for missing one, because none of them needs a credential.
