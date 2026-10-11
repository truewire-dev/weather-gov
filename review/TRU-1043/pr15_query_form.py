import asyncio, httpx
from weather_gov import Weather
from truewire_core.http import HttpClient
seen=[]
def handler(req):
  seen.append(str(req.url)); return httpx.Response(200, json={'type':'FeatureCollection','features':[]}, headers={'content-type':'application/geo+json'})
async def main():
  c = Weather.new(contact='me@x')
  c.client.http._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
  for kw in [dict(id=['KSEA','KPDX']), dict(id=('KSEA','KPDX')), dict(id=[]), dict(state=['WA'], limit=5)]:
    try: await c.stations.list_stations(**kw, validate=False)
    except Exception as e: print(kw, type(e).__name__, e)
  await c.alerts.get_active_alerts(severity=['Severe','Extreme'], region=['PA'], validate=False)
  print(*seen, sep='\n')
asyncio.run(main())
