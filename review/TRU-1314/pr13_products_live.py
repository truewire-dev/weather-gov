import asyncio, collections
from weather_gov import Weather
async def main():
  async with Weather.new(contact='hello@truewire.dev') as c:
    types = (await c.products.list_product_types())['@graph']
    sem = asyncio.Semaphore(6)
    res = collections.Counter(); fails = []; empties = []
    async def one(code):
      async with sem:
        for attempt in range(3):
          try:
            r = await c.products.list_locations_for_type(type_id=code)
            assert isinstance(r['locations'], dict), type(r['locations'])
            res['ok'] += 1
            if not r['locations']: empties.append(code)
            return
          except Exception as e:
            err = e
            await asyncio.sleep(1)
        res['fail'] += 1; fails.append((code, type(err).__name__, str(err)[:150]))
    await asyncio.gather(*(one(t['productCode']) for t in types))
    print(len(types), dict(res), 'empty:', len(empties), fails[:5])
    allloc = await c.products.list_locations()
    print('list_locations', type(allloc['locations']).__name__, len(allloc['locations']))
    two = await c.products.list_products(type=['AFD', 'ZFP'], location=['SEW'], limit=50)
    print('two types', collections.Counter(p['productCode'] for p in two['@graph']))
asyncio.run(main())
