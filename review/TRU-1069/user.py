from weather_gov.schemas import RadarHost
from weather_gov.radar.get_queue import RadarQueue
from weather_gov.radar.list_stations import ListStations

def same_host(q: RadarQueue, h: RadarHost) -> bool:
    return all(p['host'] == h for p in q['@graph'])

async def follow_doc(c: ListStations) -> None:
    await c.list_stations(stationType=['Profiler'])   # as get_profiler's doc now says

async def python_name(c: ListStations) -> None:
    await c.list_stations(station_type=['Profiler'])

bad: RadarHost = 'xds'
