from weather_gov import Weather
from weather_gov.schemas import ZoneKind


async def new_shape(client: Weather, kind: ZoneKind) -> None:
  await client.zones.get_zone('WAZ315', zone_type='forecast')
  await client.zones.get_zone('WAZ315', zone_type=kind)
  await client.zones.get_forecast('WAZ315', zone_type='public')
  await client.zones.list_transmitters('WAC033')
  await client.zones.list_zones_by_type('county', id=['WAC033'])
  await client.zones.list_zones(type=[kind])


async def old_shape(client: Weather) -> None:
  await client.zones.get_zone('forecast', zone_id='WAZ315')
  await client.zones.get_zone('WAZ315', 'forecast')
