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
  'offices.get_office[seattle]': office,
  'products.list_product_types[all]': product_types,
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
