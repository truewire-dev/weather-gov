import asyncio
from weather_gov import Weather
from weather_gov.core import ApiError, empty_map
async def main():
  async with Weather.new(contact='hello@truewire.dev') as c:
    try:
      await c.products.get_latest_product(type_id='CLI', location_id='OKX')
      print('no error')
    except ApiError as e:
      print(type(e).__name__, e)
    r = await c.products.list_products_by_type_and_location(type_id='CLI', location_id='OKX')
    print('by type+loc graph', len(r['@graph']))
asyncio.run(main())
for v, p in [({'a': []}, 'a'), ({'a': {'b': []}}, 'a.b'), ({'a': None}, 'a.b'), ([], 'a'), ({'a': [1]}, 'a'), ({}, 'a')]:
  print(v, p, '->', empty_map(v, p))
