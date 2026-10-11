import asyncio
from weather_gov import Weather
async def main():
  async with Weather.new(contact='hello@truewire.dev') as c:
    types = (await c.products.list_product_types())['@graph']
    ok = bad = 0; first = None
    for t in types[:60]:
      try:
        await c.products.list_locations_for_type(type_id=t['productCode'])
        ok += 1
      except Exception as e:
        bad += 1; first = first or (t['productCode'], type(e).__name__, str(e)[:200])
    print('ok', ok, 'failed', bad, first)
    raw = await c.products.list_locations_for_type(type_id=first[0], validate=False)
    print(raw)
asyncio.run(main())
