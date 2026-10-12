"""TRU-614: all eight radar surfaces live through the Python client, validation on."""
import asyncio, datetime as dt
import httpx
from truewire_core.exceptions import ApiError, NetworkError
from weather_gov import Weather

sent: list[str] = []
_send = httpx.AsyncClient.send
async def spy(self, req, *a, **k):
  sent.append(str(req.url)); return await _send(self, req, *a, **k)
httpx.AsyncClient.send = spy  # type: ignore[method-assign]

def kinds(v): return {type(x).__name__ for x in v} if isinstance(v, list) else type(v).__name__

async def main() -> None:
  async with Weather.new(contact='review@truewire.dev') as c:
    r = c.radar
    st = await r.list_stations(['TDWR', 'Profiler'])
    print('list_stations', sent[-1].split('?')[1], len(st['features']),
          sorted({f['properties']['stationType'] for f in st['features']}))
    s = await r.get_station(station_id='KATX'); p = s['properties']
    print('get_station', p['id'], {k: type(v).__name__ for k, v in (p.get('latency') or {}).items() if 'Time' in k})
    a = await r.list_station_alarms('KATX'); print('alarms', len(a['@graph']), [kinds(x['timestamp']) for x in a['@graph'][:1]])
    sv = await r.list_servers(); print('list_servers', len(sv['@graph']))
    one = await r.get_server(server_id='ldm1'); print('get_server', one['id'])
    sp = await r.list_spgds(); print('list_spgds ok', type(sp).__name__)
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    q = await r.get_queue('rds', limit=3, station='KATX', arrived=f'PT10M/{now}')
    g = q['@graph']; print('get_queue', sent[-1].split('?')[1], len(g),
      [(x['arrivalTime'].isoformat(), x['arrivalTime'].tzinfo is not None) for x in g[:1]])
    try:
      q2 = await r.get_queue('rds', limit=3, created=f'PT10M/{now}'); print('created ok', len(q2['@graph']))
    except (ApiError, NetworkError) as e: print('created ->', type(e).__name__, repr(e.__cause__), str(e)[:120])
    try:
      pr = await r.get_profiler(station_id='TLKA2'); print('profiler ok', type(pr).__name__, list(pr)[:5])
    except ApiError as e: print('profiler ->', type(e).__name__, str(e)[:160])

asyncio.run(main())
