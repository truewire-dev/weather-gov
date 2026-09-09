# Changelog

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
