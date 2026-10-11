import asyncio, collections
from datetime import datetime, timedelta, timezone
from weather_gov import Weather
async def main():
  fails = collections.Counter(); ex = {}
  async def t(name, coro):
    try: return await coro
    except Exception as e:
      fails[name] += 1; ex.setdefault(name, repr(e.__cause__ or e)[:400])
  async with Weather.new(contact='hello@truewire.dev') as c:
    st = await t('list_stations', c.radar.list_stations())
    ids = [f['properties']['id'] for f in st['features']]
    for k in ['WSR-88D','TDWR','Profiler']: await t('list_stations_'+k, c.radar.list_stations(station_type=[k]))
    for i in ids[::4]:
      await t('get_station', c.radar.get_station(station_id=i))
      await t('alarms', c.radar.list_station_alarms(station_id=i))
    sv = await t('list_servers', c.radar.list_servers())
    for s in sv['@graph']: await t('get_server', c.radar.get_server(server_id=s['id']))
    start = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(second=0, microsecond=0)
    await t('spgds', c.radar.list_spgds(published=f'{start:%Y-%m-%dT%H:%M:%SZ}/PT10M'))
    for h in ['rds','tds']: await t('queue_'+h, c.radar.get_queue(host=h, limit=2000))
  print(len(ids), dict(fails)); print(ex)
asyncio.run(main())
