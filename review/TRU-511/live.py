import asyncio
from datetime import datetime, timedelta, timezone

from weather_gov import Weather


async def main() -> None:
  async with Weather.new(contact='hello@truewire.dev') as client:
    zones = await client.zones.list_zones(point='47.6062,-122.3321')
    print('list_zones:', sorted((f['properties']['type'], f['properties']['id']) for f in zones['features']))
    zone = await client.zones.get_zone('forecast', zone_id='WAZ315')
    props = zone['properties']
    print('get_zone:', props['id'], props['type'], props['name'], props['effectiveDate'], type(props['effectiveDate']).__name__, zone['geometry'] and zone['geometry']['type'])
    fc = await client.zones.get_forecast('forecast', zone_id='WAZ315')
    print('get_forecast:', fc['updated'], fc['periods'][0]['name'])
    radio = await client.zones.list_transmitters(zone_id='WAC033')
    print('list_transmitters:', len(radio['@graph']), sorted({t['callSign'] for t in radio['@graph']}), type(radio['@graph'][0]['transmitterFrequency']).__name__)
    grid = await client.stations.list_stations_for_gridpoint('SEW', grid_x=125, grid_y=68, limit=3)
    print('gridpoint:', [(f['properties']['stationIdentifier'], f['properties'].get('distance', {}).get('value')) for f in grid['features']])
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    obs = await client.stations.get_observations_for_zone('WAZ315', start=end - timedelta(hours=2), end=end, limit=5)
    print('zone obs:', [(f['properties']['stationId'], f['properties']['timestamp']) for f in obs['features']])


asyncio.run(main())
