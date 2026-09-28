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
