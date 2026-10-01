"""What a user types against weather_gov.aviation; every URL the client builds is printed."""
import asyncio, json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
import httpx
from truewire_core.http import HttpClient
from weather_gov import Weather

SPEC = Path(__file__).resolve().parents[2] / 'spec/endpoints/aviation'
def body(ep, ex): return json.loads((SPEC / ep / 'examples' / f'{ex}.response.json').read_text())['payload']
seen = []
def handler(req: httpx.Request) -> httpx.Response:
  seen.append(str(req.url))
  p = req.url.raw_path.decode().split('?')[0]
  if p.endswith('/cwas') : return httpx.Response(200, json=body('list_cwas', 'fort_worth'))
  if '/cwas/' in p: return httpx.Response(200, json=body('get_cwa', 'latest'))
  if p.count('/') == 5: return httpx.Response(200, json=body('get_sigmet', 'anchorage_latest'))
  return httpx.Response(200, json=body('list_sigmets_for_atsu', 'anchorage'))

async def main():
  w = Weather.new(contact='review@truewire.dev')
  w.client.http = HttpClient(_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
  a = w.aviation
  cwa = await a.get_cwa('ZFW', date=date(2026, 9, 30), sequence=301)
  ring = cwa['geometry']['coordinates'][0] if cwa['geometry'] else []
  print('cwa pos type', type(ring[0]).__name__, ring[0], 'issueTime', repr(cwa['properties']['issueTime']))
  # date is UTC by doc; a user holding a datetime passes it (datetime is a date subclass)
  late = datetime(2026, 9, 30, 20, 0, tzinfo=timezone(timedelta(hours=-7)))  # 03:00Z on 10-01
  await a.list_sigmets_for_atsu_on_date('ANC', date=late)
  await a.list_sigmets(start=datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc))
  await a.list_sigmets(start=datetime(2026, 9, 30, 12, 0, tzinfo=timezone(timedelta(hours=-5))))
  await a.list_sigmets(start=datetime(2026, 9, 30, 12, 0))  # naive
  await a.list_sigmets(date=date(2026, 9, 30), sequence='1E')
  await a.list_sigmets()
  await a.get_sigmet(atsu='ANC', date=date(2026, 9, 30), time='20:05')  # pattern says HHMM
  await a.get_sigmet(atsu='anc/x', date=date(2026, 9, 30), time='2005')
  try:
    await a.get_cwa('ZFW', date=date(2026, 9, 30), sequence=5)  # minimum 100
  except Exception as e: print('min100 ->', type(e).__name__, e)
  try:
    await a.get_cwa('zfw', date=date(2026, 9, 30), sequence=301)  # type: ignore[arg-type]
  except Exception as e: print('enum ->', type(e).__name__, e)
  for u in seen: print(' ', u)

asyncio.run(main())
