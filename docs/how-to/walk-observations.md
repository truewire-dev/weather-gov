# Walk a span of observations

`stations.get_observations` returns what one station reported between `start` and `end`,
newest first. The service caps a response at 500 observations, keeps the newest, and says
nothing about the ones it withheld. A busy station reports every few minutes, so a day is
a few hundred observations and a week is several responses.

`stations.get_observations_paged` walks the whole span. It is declared in the spec as a
`seek` walk, so the three clients walk the same way:

1. Ask for the span.
2. If the response came back full, the span held more. Move `end` back to the oldest
   observation in it and ask again.
3. Stop at the first response that is not full.

The service's `end` is exclusive, so the next request stops just short of the observation
the last one ended on. Were the service ever to serve it again, the walk would drop it by
its timestamp, so no observation is returned twice. `start` stays where you put it.

Await the walk for every observation in the span, newest first, or iterate it for one
response at a time. Each response is one request, and nothing is fetched before you ask
for it.

## Python

Await it:

```python
from datetime import datetime, timedelta, timezone

from weather_gov import Weather


async def last_week(client: Weather) -> None:
  end = datetime.now(timezone.utc)
  observations = await client.stations.get_observations_paged(
    'KSEA', start=end - timedelta(days=7), end=end
  )
  print(len(observations), 'observations')
```

Or iterate it:

```python
from datetime import datetime, timedelta, timezone

from weather_gov import Weather


async def six_hours(client: Weather) -> None:
  end = datetime.now(timezone.utc)
  async for page in client.stations.get_observations_paged(
    'KSEA', start=end - timedelta(hours=6), end=end
  ):
    for feature in page:
      observation = feature['properties']
      print(observation['timestamp'], observation['temperature']['value'])
```

## TypeScript

The walk is a `PromiseLike` and an `AsyncIterable`. Awaited, it returns every row;
iterated, it yields each response's rows.

```ts
import { Weather } from '@truewire/weather-gov'

const client = Weather.new({ contact: 'you@example.com' })
const end = new Date()
const start = new Date(end.getTime() - 7 * 24 * 60 * 60 * 1000)

const week = await client.stations.getObservationsPaged({ station_id: 'KSEA', start, end })
console.log(week.length, 'observations')

for await (const page of client.stations.getObservationsPaged({ station_id: 'KSEA', start, end })) {
  for (const feature of page) {
    console.log(feature.properties.timestamp.toISOString(), feature.properties.temperature.value)
  }
}
```

## Rust

The walk is a future for every row, and `rows()` is a `futures::Stream` of one response's
rows at a time. `pages()` also carries each response's state. `.next()` needs
`futures::StreamExt` in scope. The timestamps are `truewire_core` types, so this needs
`futures` and `truewire-core` in your own `Cargo.toml`.

```rust
use futures::StreamExt;
use truewire_core::chrono::{Duration, Utc};
use truewire_core::{CallOptions, TimestampIso};
use weather_gov::{stations, Weather};

async fn last_week(client: &Weather) -> truewire_core::Result<()> {
    let now = Utc::now();
    let request = stations::get_observations::Request {
        station_id: "KSEA".to_string(),
        start: Some(TimestampIso(now - Duration::days(7))),
        end: Some(TimestampIso(now)),
        ..Default::default()
    };
    let walk = client
        .stations
        .get_observations_paged(request, CallOptions::default());

    let all = walk.clone().await?;
    println!("{} observations", all.len());

    let mut pages = walk.rows();
    while let Some(page) = pages.next().await {
        println!("{} in this response", page?.len());
    }
    Ok(())
}
```

## Things to know

- **The service keeps about a week.** A `start` older than that returns nothing rather
  than failing, so a walk over last month returns only the last week.
- **Leave `limit` out.** It defaults to the service's cap of 500, which means the fewest
  requests. A smaller `limit` makes more of them. The walk raises a `limit` below 2 to 2,
  since each response has to hold one new observation beside the one it re-reads.
- **Leave `end` out for "until now".** Without an `end`, the walk starts at the newest
  observation the station has.
