# Weather

The [US National Weather Service API](https://www.weather.gov/documentation/services-web-api)
serves the forecasts, the hourly forecasts, the raw gridded data behind both, observations
from every reporting station, and every watch, warning and advisory in effect. This client
covers nineteen of its endpoints, in Python, TypeScript and Rust, generated from one spec.

| Call | What it returns |
| --- | --- |
| `points.get_point` | the forecast grid cell a latitude and longitude fall in |
| `forecast.get_forecast` | the twice-daily narrative forecast for a grid cell |
| `forecast.get_hourly_forecast` | one period per hour for about the next week |
| `forecast.get_grid_data` | the raw series both forecasts are rendered from |
| `stations.list_stations` | the observation stations, optionally narrowed |
| `stations.get_observations` | what one station reported over a span, newest first |
| `stations.get_latest_observation` | the most recent observation from one station |
| `alerts.get_active_alerts` | every watch, warning and advisory in effect, optionally narrowed |
| `alerts.get_alert` | one alert, with its polygon when it has one |
| `offices.get_office` | one forecast office and what it is responsible for |
| `products.list_product_types` | every kind of text product the service issues |

`stations.get_observations_paged` walks a whole span
([Walk a span of observations](how-to/walk-observations.md)). The
[reference](reference/index.md) lists every call with its upstream path.

## Why a validated client

The service answers in three vocabularies: GeoJSON for most of it, schema.org for the
offices, JSON-LD for the product types. The spec describes each as it actually arrives,
recorded from real responses, and the client checks every response against it. A field
the service stops sending fails at the call, not later as a `KeyError`.

- **Every measurement carries its unit.** A temperature is
  `{'unitCode': 'wmoUnit:degC', 'value': 13, 'qualityControl': 'V'}`, and `value` is `None`
  wherever the measurement is missing rather than zero. The types say so.
- **The wrapper is gone where it carried nothing.** A forecast's GeoJSON `geometry` is the
  outline of the grid cell you named, so `get_forecast` returns the forecast itself. An
  alert's polygon is data, so alerts come back whole.
- **The filters are enumerations.** `status` takes `actual` while `severity` takes
  `Severe`. The spellings come from the service's own error replies, so a wrong case is a
  type error, not a 400.
- **Errors say which parameter.** A bad value the types cannot catch comes back as a
  `BadRequest` that leads with the service's `parameterErrors`.

## First call

Almost everything is addressed by grid cell rather than by coordinates, so a caller
starts at `points.get_point`:

```python
import asyncio

from weather_gov import Weather


async def main() -> None:
  async with Weather.new(contact='you@example.com') as client:
    point = await client.points.get_point(latitude=47.6062, longitude=-122.3321)

    forecast = await client.forecast.get_forecast(
      office=point['gridId'], grid_x=point['gridX'], grid_y=point['gridY']
    )
    for period in forecast['periods'][:3]:
      print(
        period['name'], period['temperature'], period['temperatureUnit'], period['shortForecast']
      )


asyncio.run(main())
```

The same call in TypeScript and Rust is in the quickstart (`docs.yml`) and in each
package's README. No key is needed, only a contact: [API keys](api-keys.md) explains why.

## Install

| Language | Package | Import |
| --- | --- | --- |
| Python 3.11+ | `pip install truewire-weather-gov` | `weather_gov` |
| TypeScript, Node 20+ | `npm install @truewire/weather-gov` | `@truewire/weather-gov` |
| Rust | `truewire-weather-gov` on crates.io | `weather_gov` |

PyPI also has an unrelated `weather-gov` package that imports as `weather_gov`. The two
cannot share an environment.
