# Reference

Eight groups, twenty-six endpoints, every one recorded against the live API. Each signature is
generated from the endpoint's schema, so the types in your editor are the reference: every
field carries its description, and every method's docstring links the service's own page
for the endpoint.

**Returns** says what a call hands back. *Unwrapped* endpoints answer in a GeoJSON
`Feature` whose `geometry` only repeats what you asked for, so the client returns the
`properties`. *Whole* endpoints return the body as it arrived, because its wrapper is data.

## `points`

| Endpoint | Upstream | Returns |
| --- | --- | --- |
| `get_point` | `GET /points/{latitude},{longitude}` | unwrapped: the grid cell, office and time zone |

## `forecast`

| Endpoint | Upstream | Returns |
| --- | --- | --- |
| `get_forecast` | `GET /gridpoints/{office}/{grid_x},{grid_y}/forecast` | unwrapped: about a dozen named periods |
| `get_hourly_forecast` | `GET /gridpoints/{office}/{grid_x},{grid_y}/forecast/hourly` | unwrapped: one period per hour |
| `get_grid_data` | `GET /gridpoints/{office}/{grid_x},{grid_y}` | unwrapped: the raw series, each with its unit |

## `stations`

| Endpoint | Upstream | Returns |
| --- | --- | --- |
| `list_stations` | `GET /stations` | whole: a feature collection of stations |
| `get_observations` | `GET /stations/{station_id}/observations` | whole: a feature collection, newest first |
| `get_latest_observation` | `GET /stations/{station_id}/observations/latest` | unwrapped: one observation |
| `list_stations_for_zone` | `GET /zones/forecast/{zone_id}/stations` | whole: the stations in a public zone |
| `list_stations_for_gridpoint` | `GET /gridpoints/{office}/{grid_x},{grid_y}/stations` | whole: stations nearest a grid cell, with distance and bearing |
| `get_observations_for_zone` | `GET /zones/forecast/{zone_id}/observations` | whole: every station of a zone, merged newest first |

`get_observations` has a paged twin, `get_observations_paged`, which walks a whole span
by moving `end` ([Walk a span of observations](../how-to/walk-observations.md)).
`get_observations_for_zone` has none: its stations report on the same minutes and its
`end` is exclusive, so a walk would skip rows. Walk each station instead.

## `alerts`

| Endpoint | Upstream | Returns |
| --- | --- | --- |
| `get_active_alerts` | `GET /alerts/active` | whole: a feature collection of alerts |
| `get_alert` | `GET /alerts/{id}` | whole: one alert, with its polygon when it has one |

`status`, `region`, `severity`, `urgency` and `certainty` are enumerations spelled as the
service spells them: `actual`, but `Severe`, `Immediate` and `Likely`.

## `offices`

| Endpoint | Upstream | Returns |
| --- | --- | --- |
| `get_office` | `GET /offices/{office_id}` | whole: one office, in schema.org JSON-LD |

## `products`

| Endpoint | Upstream | Returns |
| --- | --- | --- |
| `list_product_types` | `GET /products/types` | whole: every text product code, in JSON-LD |

## `zones`

| Endpoint | Upstream | Returns |
| --- | --- | --- |
| `list_zones` | `GET /zones` | whole: zones of every type, filtered, without outlines |
| `list_zones_by_type` | `GET /zones/{zone_type}` | whole: the same, of one type |
| `get_zone` | `GET /zones/{zone_type}/{zone_id}` | whole: one zone, with its outline |
| `get_forecast` | `GET /zones/{zone_type}/{zone_id}/forecast` | unwrapped: a public zone's text forecast |
| `list_transmitters` | `GET /zones/{zone_type}/{zone_id}/radio` | whole: a county's weather radio transmitters, in JSON-LD |

Array filters take one value each until TRU-495: the service reads several only
comma-separated.

## `radar`

| Endpoint | Upstream | Returns |
| --- | --- | --- |
| `list_stations` | `GET /radar/stations` | whole: every radar, with its latency and status |
| `get_station` | `GET /radar/stations/{station_id}` | whole: one radar, with its maintenance reports |
| `list_station_alarms` | `GET /radar/stations/{station_id}/alarms` | whole: a radar's alarm log, newest first, in JSON-LD |
| `list_servers` | `GET /radar/servers` | whole: the data distribution servers and their health, in JSON-LD |
| `get_server` | `GET /radar/servers/{server_id}` | whole: one server |
| `get_queue` | `GET /radar/queues/{host}` | whole: the Level II products through one host's queue, in JSON-LD |
| `list_spgds` | `GET /radar/spgds` | whole: status reports from the SPG data servers, in JSON-LD |

`get_queue` and `list_spgds` take ISO 8601 intervals as strings, such as
`2026-09-30T23:00:00Z/PT10M`, and the service keeps about a week of either. The SPG
reports send their times as Unix seconds in strings; the clients parse them into real
times. `GET /radar/profilers/{stationId}` is not here: it answers 404 for every profiler.

## In each language

The names above are Python's. The groups are the same in every language, and each
method follows its language's convention:

| Python | TypeScript | Rust |
| --- | --- | --- |
| `client.stations.get_observations_paged('KSEA', ...)` | `client.stations.getObservationsPaged({ station_id: 'KSEA', ... })` | `client.stations.get_observations_paged(Request { .. }, CallOptions::default())` |
| keyword arguments | one request object, wire names | one `Request` struct, `..Default::default()` |
| a `TypedDict`, wire names | an interface, wire names, `Date` for timestamps | a struct, snake_case fields |

Every call takes `validate`, `True` by default. `False` returns the body as the service
sent it, typed `Any` in Python and `unknown` in TypeScript. `Weather.new(validate=False)`
makes that the client's default. In Rust each method has a `_raw` twin, such as
`get_office_raw`, that returns the body as a `serde_json::Value`.

## Errors

A non-2xx answer raises the runtime's error for its status: `BadRequest` for a 400,
`RateLimited` for a 429, and `ApiError` for any other. Rust returns the same kinds as an
`Error` with the status and body attached. The service answers errors as RFC 7807 problem
details, and a bad parameter adds a `parameterErrors` list, which the message leads with:

```text
GET /alerts/active: HTTP 400: query.zone[0]: Does not match the regex pattern
^(A[KLMNRSZ]|C[AOT]|D[CE]|...)[CZ]\d{3}$
```
