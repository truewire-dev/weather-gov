"""What each recording proves about the typed result, beyond validating.

One test per example request, driven through the real client against the mock. Validation
is already covered by `test_examples_replay.py`; these assertions are about meaning -- that
`gridId` really is the office code the forecast endpoints take, that an observation's
temperature really arrives beside a unit, that the alert filters really filtered.

The assertions are structural. The numbers here (74 observations, 33 alerts) move with
every re-recording; what does not move is that the shape is the shape. Where a count is
asserted it is because the count is the point -- a `limit` that was honoured, a page that
came back full.
"""

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
from truewire.examples import run_example_request
from truewire.spec.repo import endpoint_records, load_request_example
from typing_extensions import Any

PROJECT = Path(__file__).resolve().parents[3]

WMO = 'wmoUnit:'
"""Every unit code in this API is a WMO shorthand. A measurement without one is not a
measurement, and the schema says so by making `unitCode` required."""


def is_measurement(value: Any, *, unit: str | None = None) -> None:
  """A `QuantitativeValue`: a unit, and a number or an honest null."""
  assert value['unitCode'].startswith(WMO)
  assert value['value'] is None or isinstance(value['value'], (int, float))
  if unit is not None:
    assert value['unitCode'] == unit


def as_datetime(value: Any) -> datetime:
  """A timestamp as the client hands it back, or as a request example writes it."""
  return value if isinstance(value, datetime) else datetime.fromisoformat(value)


def is_point(geometry: Any) -> None:
  longitude, latitude = geometry['coordinates']
  assert geometry['type'] == 'Point'
  assert -180 <= longitude <= 180
  assert -90 <= latitude <= 90


def point(result: Any) -> None:
  """The entry point of the whole API: coordinates in, a grid address out."""
  assert result['gridId'] == 'SEW'
  assert (result['gridX'], result['gridY']) == (125, 68)
  assert result['timeZone'] == 'America/Los_Angeles'
  assert result['forecast'].endswith('/gridpoints/SEW/125,68/forecast')
  # The wrapper is gone: this is the declared envelope working, not a nested `properties`.
  assert 'properties' not in result
  nearest = result['relativeLocation']['properties']
  assert nearest['city'] == 'Seattle' and nearest['state'] == 'WA'
  is_measurement(nearest['distance'], unit='wmoUnit:m')


def forecast(result: Any) -> None:
  """Fourteen periods: a week of days and nights, each with prose and a bare temperature."""
  periods = result['periods']
  assert len(periods) == 14
  assert result['units'] == 'us'
  assert [p['number'] for p in periods] == list(range(1, 15))
  assert any(p['isDaytime'] for p in periods) and any(not p['isDaytime'] for p in periods)
  for period in periods:
    # The one place this API sends a bare number beside a unit *string*, and the schema
    # types it that way rather than pretending it is a QuantitativeValue.
    assert isinstance(period['temperature'], (int, float))
    assert period['temperatureUnit'] == 'F'
    assert period['shortForecast']
    is_measurement(period['probabilityOfPrecipitation'], unit='wmoUnit:percent')


def hourly_forecast(result: Any) -> None:
  """The same shape, one period per hour, filling the fields the narrative one leaves out."""
  periods = result['periods']
  assert len(periods) > 100
  first = periods[0]
  assert first['name'] == '' and first['detailedForecast'] == ''
  is_measurement(first['dewpoint'], unit='wmoUnit:degC')
  is_measurement(first['relativeHumidity'], unit='wmoUnit:percent')


def grid_data(result: Any) -> None:
  """The raw series the narrative forecasts are rendered from."""
  assert result['gridId'] == 'SEW'
  temperature = result['temperature']
  assert temperature['uom'].startswith(WMO)
  assert len(temperature['values']) > 20
  for entry in temperature['values'][:5]:
    # A `validTime` is an interval, not an instant: `<start>/<duration>`. That is why it
    # carries no timestamp format and stays a string.
    start, _, duration = entry['validTime'].partition('/')
    assert start and duration.startswith('P')
  weather = result['weather']['values'][0]['value']
  assert isinstance(weather, list)
  for phenomenon in weather:
    assert set(phenomenon) >= {'coverage', 'weather', 'intensity'}


def stations(result: Any) -> None:
  """A page of Washington stations, and the identifier the observation endpoints take."""
  features = result['features']
  assert result['type'] == 'FeatureCollection'
  assert len(features) == 20
  for feature in features:
    is_point(feature['geometry'])
    assert feature['properties']['stationIdentifier']
    assert feature['properties']['name']
  # The wrapper this project cannot page from, kept in the schema so it is visible.
  assert result['pagination']['next'].startswith('https://api.weather.gov/stations?')


def latest_observation(result: Any) -> None:
  """Current conditions at an airport station, every measurement beside its unit."""
  assert result['stationId'] == 'KSEA'
  assert result['timestamp']
  is_measurement(result['temperature'], unit='wmoUnit:degC')
  is_measurement(result['dewpoint'], unit='wmoUnit:degC')
  is_measurement(result['windSpeed'], unit='wmoUnit:km_h-1')
  # A null measurement is the normal case, not an error: there is no gust unless it gusted.
  assert 'value' in result['windGust']
  for layer in result['cloudLayers']:
    assert layer['amount'] in ('OVC', 'BKN', 'SCT', 'FEW', 'SKC', 'CLR', 'VV')
    is_measurement(layer['base'], unit='wmoUnit:m')


def observations(result: Any) -> None:
  """Six hours of KSEA, newest first."""
  features = result['features']
  # The count moves with every re-recording, and is deliberately not pinned here. What is
  # pinned is that the window sits under the service's cap of 500 -- if it stopped doing
  # so the walk's truncation guard would start firing on the example that is meant to show
  # the walk succeeding.
  assert 0 < len(features) < 500
  timestamps = [f['properties']['timestamp'] for f in features]
  assert timestamps == sorted(timestamps, reverse=True), 'the service answers newest first'
  for feature in features:
    is_point(feature['geometry'])
    is_measurement(feature['properties']['temperature'])


def capped_observations(result: Any) -> None:
  """The same six hours asked for ten rows at a time: what truncation looks like on the
  wire. The service returns exactly the cap and says nothing about the rest, which is what
  the walk's guard exists to catch."""
  cap = json.loads(
    (
      PROJECT / 'spec/endpoints/stations/get_observations/examples/ksea_capped.request.json'
    ).read_text()
  )['request']['limit']
  assert len(result['features']) == cap


def active_alerts(result: Any) -> None:
  """Severe alerts in effect nationwide, and proof the filters were applied."""
  features = result['features']
  assert result['type'] == 'FeatureCollection'
  assert features, 'no severe alert was in effect anywhere when this was recorded'
  for feature in features:
    alert = feature['properties']
    assert alert['severity'] == 'Severe', 'the capitalised filter was honoured'
    assert alert['status'] == 'Actual', 'the lower-case filter was honoured'
    assert alert['id'].startswith('urn:oid:')
    assert alert['event'] and alert['description']
    # An alert covers zones or a polygon, never neither.
    assert feature['geometry'] is not None or alert['affectedZones']


def one_alert(result: Any) -> None:
  """The same alert fetched by its own identifier, kept whole: its geometry is real data."""
  assert result['type'] == 'Feature'
  alert = result['properties']
  assert alert['id'].startswith('urn:oid:')
  assert alert['severity'] == 'Severe'
  if result['geometry'] is not None:
    assert result['geometry']['type'] in ('Polygon', 'MultiPolygon')


def office(result: Any) -> None:
  """A schema.org organisation, not a GeoJSON feature -- a different vocabulary, typed as it
  actually arrives."""
  assert result['id'] == 'SEW'
  assert result['address']['addressRegion'] == 'WA'
  assert result['responsibleForecastZones']
  assert result['approvedObservationStations']


def product_types(result: Any) -> None:
  """JSON-LD: a third vocabulary in the same API."""
  graph = result['@graph']
  assert len(graph) > 300
  codes = {entry['productCode'] for entry in graph}
  assert {'AFD', 'TOR'} <= codes
  for entry in graph:
    assert entry['productName']


def example_request(endpoint: str, example_id: str) -> Any:
  """The request half of an example, for a test that checks the answer against what was
  asked rather than against a constant the refresh would move."""
  path = PROJECT / 'spec/endpoints' / endpoint.replace('.', '/') / 'examples'
  return json.loads((path / f'{example_id}.request.json').read_text())['request']


def is_zone(feature: Any, *, geometry: bool) -> Any:
  """A zone feature: its URL is its code, and a list leaves the outline out."""
  zone = feature['properties']
  assert feature['type'] == 'Feature'
  assert feature['id'] == zone['@id'] and zone['@id'].endswith('/' + zone['id'])
  assert zone['name']
  assert zone['effectiveDate'] < zone['expirationDate']
  if geometry:
    assert feature['geometry']['type'] in ('Polygon', 'MultiPolygon')
  else:
    assert feature['geometry'] is None
  return zone


def zones_at_point(result: Any) -> None:
  """A point lies in exactly one zone of each kind a land point has."""
  zones = [is_zone(feature, geometry=False) for feature in result['features']]
  assert sorted(zone['type'] for zone in zones) == ['county', 'fire', 'public']
  assert {zone['id'] for zone in zones} >= {'WAZ315', 'WAC033'}
  assert all(zone['state'] == 'WA' for zone in zones)


def zones_filtered(result: Any) -> None:
  """Every filter held: the area, the type and the limit, and the service's order by code."""
  asked = example_request('zones.list_zones', 'washington_fire')
  zones = [is_zone(feature, geometry=False) for feature in result['features']]
  assert len(zones) == asked['limit']
  assert all(zone['state'] == 'WA' and zone['type'] == 'fire' for zone in zones)
  assert [zone['id'] for zone in zones] == sorted(zone['id'] for zone in zones)


def zones_of_type(result: Any) -> None:
  """The type comes from the path; county codes carry a `C` where public ones carry a `Z`."""
  asked = example_request('zones.list_zones_by_type', 'washington_counties')
  zones = [is_zone(feature, geometry=False) for feature in result['features']]
  assert len(zones) == asked['limit']
  for zone in zones:
    assert zone['type'] == 'county' and zone['state'] == 'WA'
    assert zone['id'].startswith('WAC')


def zone(result: Any) -> None:
  """One zone, whole: the outline is the point of fetching it alone."""
  seattle = is_zone(result, geometry=True)
  assert (seattle['id'], seattle['type'], seattle['name']) == (
    'WAZ315',
    'public',
    'City of Seattle',
  )
  assert seattle['gridIdentifier'] == 'SEW'
  assert seattle['forecastOffice'].endswith('/offices/SEW')
  assert seattle['timeZone'] == ['America/Los_Angeles']
  assert any(url.endswith('/stations/KSEA') for url in seattle['observationStations'])
  # A polygon's rings close on themselves.
  ring = result['geometry']['coordinates'][0]
  assert ring[0] == ring[-1] and len(ring) > 3


def zone_forecast(result: Any) -> None:
  """The zone's own forecast, unwrapped: numbered periods of the forecaster's prose."""
  assert 'properties' not in result
  assert result['zone'].endswith('/zones/forecast/WAZ315')
  periods = result['periods']
  assert len(periods) > 6
  assert [p['number'] for p in periods] == list(range(1, len(periods) + 1))
  for period in periods:
    assert period['name'] and period['detailedForecast']


def transmitters(result: Any) -> None:
  """Every transmitter broadcasts for the county asked about, repeats and all."""
  graph = result['@graph']
  assert graph
  for transmitter in graph:
    assert 'WAC033' in transmitter['counties']
    assert len(transmitter['sameCodes']) == len(transmitter['counties'])
    # NOAA Weather Radio broadcasts on seven channels, 162.400 to 162.550 MHz.
    assert 162 < transmitter['transmitterFrequency'] < 163
  assert 'KHB60' in {transmitter['callSign'] for transmitter in graph}


def zone_observations(result: Any) -> None:
  """Several stations, merged newest first, capped at the limit, inside the window."""
  asked = example_request('stations.get_observations_for_zone', 'seattle_capped')
  features = result['features']
  assert len(features) == asked['limit']
  timestamps = [f['properties']['timestamp'] for f in features]
  assert timestamps == sorted(timestamps, reverse=True), 'the service answers newest first'
  start = datetime.fromisoformat(asked['start'])
  end = datetime.fromisoformat(asked['end'])
  assert all(start <= stamp < end for stamp in timestamps)
  assert len({f['properties']['stationId'] for f in features}) > 1
  # Timestamps repeat across stations: why this endpoint declares no seek walk.
  assert len(set(timestamps)) < len(timestamps)
  for feature in features:
    is_point(feature['geometry'])
    is_measurement(feature['properties']['temperature'])


def zone_stations(result: Any) -> None:
  """The stations of a zone: the list the zone itself names, not the stations that name it
  as their own forecast zone (four of Seattle's six name a neighbouring zone)."""
  features = result['features']
  assert features
  for feature in features:
    is_point(feature['geometry'])
    assert feature['properties']['stationIdentifier']
  urls = [feature['id'] for feature in features]
  assert result['observationStations'] == urls
  zone = json.loads(
    (PROJECT / 'spec/endpoints/zones/get_zone/examples/seattle.response.json').read_text()
  )['payload']['properties']
  assert zone['id'] == example_request('stations.list_stations_for_zone', 'seattle')['zone_id']
  assert sorted(urls) == sorted(zone['observationStations'])


def gridpoint_stations(result: Any) -> None:
  """Nearest first, each with the distance and bearing only this endpoint sends."""
  asked = example_request('stations.list_stations_for_gridpoint', 'seattle_nearest')
  features = result['features']
  assert len(features) == asked['limit']
  distances = []
  for feature in features:
    station = feature['properties']
    is_measurement(station['distance'], unit='wmoUnit:m')
    is_measurement(station['bearing'], unit='wmoUnit:degree_(angle)')
    distances.append(station['distance']['value'])
  assert distances == sorted(distances)


def alert_list(result: Any) -> None:
  """One page of the last week's alerts, cut to the recorded `limit`, newest first, with the
  link to the next page the service always attaches."""
  example = example_request('alerts.list_alerts', 'first_page')
  features = result['features']
  assert len(features) == example['limit'], 'the limit was honoured'
  sent = [as_datetime(feature['properties']['sent']) for feature in features]
  assert sent == sorted(sent, reverse=True), 'the service answers newest first by `sent`'
  start, end = as_datetime(example['start']), as_datetime(example['end'])
  assert all(start <= moment <= end for moment in sent), 'the window was honoured'
  assert all(feature['properties']['status'] == 'Actual' for feature in features)
  assert 'cursor=' in result['pagination']['next']


def active_alert_count(result: Any) -> None:
  """Counts that add up: land plus marine is the total, and the marine regions split the
  marine count between them."""
  assert result['total'] == result['land'] + result['marine']
  assert sum(result['regions'].values()) == result['marine']
  assert set(result['regions']) <= {'AL', 'AT', 'GL', 'GM', 'PA', 'PI'}
  assert result['zones'] and result['areas']


def ugc_codes(result: Any) -> list[list[str]]:
  """Each alert's zone and county codes, asserting there is at least one alert."""
  features = result['features']
  assert result['type'] == 'FeatureCollection'
  assert features, 'nothing was in effect there when this was recorded'
  return [feature['properties']['geocode']['UGC'] for feature in features]


MARINE_REGIONS = {
  'AL': ('PK',),
  'AT': ('AM', 'AN'),
  'GL': ('LC', 'LE', 'LH', 'LM', 'LO', 'LS', 'SL'),
  'GM': ('GM',),
  'PA': ('PZ',),
  'PI': ('PH', 'PM', 'PS'),
}
"""The marine areas each region groups, from the OpenAPI's `MarineRegionCode`."""


def zone_alerts(result: Any) -> None:
  """Alerts for the zone in the path. Not every one names it: a county's alerts include
  ones issued for the forecast zones overlapping it (measured 2026-09-30, `AZC009`: six of
  seven listed the county), so each is held to the zone's state or marine area and at least
  one to the zone itself."""
  zone = example_request('alerts.get_active_alerts_for_zone', 'in_effect')['zone_id']
  codes = ugc_codes(result)
  assert any(zone in alert for alert in codes)
  for alert in codes:
    assert any(code.startswith(zone[:2]) for code in alert)


def area_alerts(result: Any) -> None:
  """Every alert returned covers part of the area in the path; it may cover a neighbour
  too. The path variants take no filters, so drills and test messages come back as well."""
  area = example_request('alerts.get_active_alerts_for_area', 'in_effect')['area']
  for alert in ugc_codes(result):
    assert any(code.startswith(area) for code in alert)


def region_alerts(result: Any) -> None:
  """Every alert returned covers one of the marine areas the region in the path groups."""
  region = example_request('alerts.get_active_alerts_for_region', 'in_effect')['region']
  for alert in ugc_codes(result):
    assert any(code.startswith(MARINE_REGIONS[region]) for code in alert)


def alert_types(result: Any) -> None:
  """The event names the `event` filter takes, each once."""
  types = result['eventTypes']
  assert len(types) > 100
  assert len(set(types)) == len(types)
  assert {'Tornado Warning', 'Severe Thunderstorm Warning', 'Winter Storm Watch'} <= set(types)


def glossary(result: Any) -> None:
  """The whole glossary in one response."""
  terms = result['glossary']
  assert len(terms) > 3000
  assert any(entry['term'] == '1-2-3 Rule' for entry in terms)
  for entry in terms:
    assert entry['term'] and entry['definition']


PROVES: dict[str, Callable[[Any], None]] = {
  'points.get_point[seattle]': point,
  'forecast.get_forecast[seattle]': forecast,
  'forecast.get_hourly_forecast[seattle]': hourly_forecast,
  'forecast.get_grid_data[seattle]': grid_data,
  'stations.list_stations[washington]': stations,
  'stations.get_latest_observation[ksea]': latest_observation,
  'stations.get_observations[ksea_window]': observations,
  'stations.get_observations[ksea_capped]': capped_observations,
  'alerts.get_active_alerts[severe]': active_alerts,
  'alerts.get_alert[one]': one_alert,
  'alerts.list_alerts[first_page]': alert_list,
  'alerts.count_active_alerts[now]': active_alert_count,
  'alerts.get_active_alerts_for_zone[in_effect]': zone_alerts,
  'alerts.get_active_alerts_for_area[in_effect]': area_alerts,
  'alerts.get_active_alerts_for_region[in_effect]': region_alerts,
  'alerts.list_alert_types[all]': alert_types,
  'offices.get_office[seattle]': office,
  'products.list_product_types[all]': product_types,
  'glossary.list_terms[all]': glossary,
  'zones.list_zones[seattle]': zones_at_point,
  'zones.list_zones[washington_fire]': zones_filtered,
  'zones.list_zones_by_type[washington_counties]': zones_of_type,
  'zones.get_zone[seattle]': zone,
  'zones.get_forecast[seattle]': zone_forecast,
  'zones.list_transmitters[king_county]': transmitters,
  'stations.get_observations_for_zone[seattle_capped]': zone_observations,
  'stations.list_stations_for_zone[seattle]': zone_stations,
  'stations.list_stations_for_gridpoint[seattle_nearest]': gridpoint_stations,
}
"""What each recording is here to prove. A recording nobody asserts anything about is a
file that turns green whatever the API sends."""


def recorded_requests() -> list[Any]:
  """Every example request in the project, recorded or not, as a pytest param."""
  params = []
  spec = PROJECT / 'spec'
  for record in endpoint_records(PROJECT):
    function = record.endpoint.resolved_function(record.path, spec)
    for request in sorted((record.path.parent / 'examples').glob('*.request.json')):
      example_id = request.name.removesuffix('.request.json')
      params.append(pytest.param(record, request, id=f'{function}[{example_id}]'))
  return params


def test_every_request_has_an_assertion():
  """A new example needs a `PROVES` entry, or its recording proves nothing here."""
  assert {param.id for param in recorded_requests()} == set(PROVES)


@pytest.mark.asyncio
@pytest.mark.parametrize('record,request_file', recorded_requests())
async def test_recording(client, record, request_file, request):
  """Replay one recorded call through the client and assert what it means.

  Nothing here is allowed to skip: every endpoint of this API answers without credentials,
  so a missing recording is a failure rather than an excused gap.
  """
  response_file = request_file.with_name(
    request_file.name.replace('.request.json', '.response.json')
  )
  assert response_file.exists(), f'{request_file.name} has no recorded response'
  assert json.loads(response_file.read_text())['status'] == 200
  async with client:
    result = await run_example_request(
      client,
      record.endpoint,
      load_request_example(request_file),
      client_root=PROJECT,
      endpoint_path=record.path,
    )
  PROVES[request.node.callspec.id](result)
