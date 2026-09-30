"""The positional argument of each zone endpoint that addresses one zone.

Prints `zone_type` at c85390f (`get_zone('forecast', zone_id='WAZ315')`); after the fix it
should print `zone_id` (`get_zone('WAZ315', zone_type='forecast')`).
"""

import inspect

from weather_gov.zones import Zones

for name in ('get_zone', 'get_forecast', 'list_transmitters'):
  first = list(inspect.signature(getattr(Zones, name)).parameters)[1]
  print(f'{name}: {first}')
