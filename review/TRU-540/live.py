import asyncio

from weather_gov import Weather


async def main() -> None:
  async with Weather.new(contact='hello@truewire.dev') as client:
    zone = await client.zones.get_zone('WAZ315', zone_type='forecast')
    p = zone['properties']
    print('get_zone:', p['id'], p['type'], p['name'], p['effectiveDate'], type(p['effectiveDate']).__name__, zone['geometry'] and zone['geometry']['type'])
    fc = await client.zones.get_forecast('WAZ315', zone_type='forecast')
    print('get_forecast:', fc['updated'], fc['periods'][0]['name'])
    radio = await client.zones.list_transmitters('WAC033')
    print('list_transmitters:', len(radio['@graph']), sorted({t['callSign'] for t in radio['@graph']}))


asyncio.run(main())
