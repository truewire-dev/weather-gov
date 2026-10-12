from datetime import datetime
from typing_extensions import Any, assert_type
from weather_gov import Weather
from weather_gov.radar.get_queue import RadarQueue

async def f(c: Weather) -> None:
  q = await c.radar.get_queue('rds', limit=1)
  assert_type(q, RadarQueue)
  t: datetime = q['@graph'][0]['arrivalTime']
  raw = await c.radar.get_queue('rds', validate=False)
  assert_type(raw, Any)
  p = await c.radar.get_profiler(station_id='TLKA2')
  assert_type(p, Any)
  await c.radar.get_queue('xyz')  # expect error: not rds|tds
  await c.radar.list_stations('TDWR')  # expect error: list[str]
  await c.radar.get_station('KATX')  # positional rejected
