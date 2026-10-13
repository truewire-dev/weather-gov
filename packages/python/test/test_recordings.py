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
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from decimal import Decimal
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


def stations_by_id(result: Any) -> None:
  """Two identifiers in one filter, and both stations back. The service reads `id=KSEA,KPDX`
  and keeps only the last of a repeated key, so a client sending `id=KSEA&id=KPDX` would get
  KPDX alone. The mock expects the comma form (`match.query_arrays`), so this also fails if
  the core stops joining."""
  asked = example_request('stations.list_stations', 'two_ids')
  assert len(asked['id']) == 2
  returned = [feature['properties']['stationIdentifier'] for feature in result['features']]
  assert sorted(returned) == sorted(asked['id'])


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


def zones_by_id(result: Any) -> None:
  """Two zone codes in one filter, and both zones back, of two different types: the filter
  is "any of", sent as one comma-separated item (see `stations_by_id`)."""
  asked = example_request('zones.list_zones', 'two_ids')
  assert len(asked['id']) == 2
  zones = [is_zone(feature, geometry=False) for feature in result['features']]
  assert sorted(zone['id'] for zone in zones) == sorted(asked['id'])
  assert {zone['type'] for zone in zones} == {'public', 'county'}


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


def alert_second_page(result: Any) -> None:
  """The decoded cursor advances within the same filtered window."""
  alert_list(result)
  first = json.loads(
    (PROJECT / 'spec/endpoints/alerts/list_alerts/examples/first_page.response.json').read_text()
  )['payload']['features']
  assert {row['id'] for row in first}.isdisjoint(row['id'] for row in result['features'])
  assert max(as_datetime(row['properties']['sent']) for row in result['features']) <= min(
    as_datetime(row['properties']['sent']) for row in first
  )


def null_description(result: Any) -> None:
  """A real upstream null, not a mutation of a non-null recording."""
  assert result['type'] == 'Feature'
  assert result['properties']['id'] == example_request('alerts.get_alert', 'null_description')['id']
  assert result['properties']['description'] is None


def null_response(result: Any) -> None:
  """A Civil Emergency Message has no CAP action recommendation."""
  assert result['type'] == 'Feature'
  assert result['properties']['id'] == example_request('alerts.get_alert', 'null_response')['id']
  assert result['properties']['event'] == 'Civil Emergency Message'
  assert result['properties']['response'] is None


def active_alert_count(result: Any) -> None:
  """Land plus marine is the total, and the regions listed are the marine regions with an
  alert in effect. The regions need not add up to the marine count: on 2026-10-13 all 20
  samples had them one over, `GL` counting 12 while `/alerts/active?region=GL` listed 11."""
  assert result['total'] == result['land'] + result['marine']
  assert all(count > 0 for count in result['regions'].values())
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


def recorded_payload(endpoint: str, example_id: str) -> Any:
  """The response half of another example, as it came off the wire."""
  path = PROJECT / 'spec/endpoints' / endpoint.replace('.', '/') / 'examples'
  return json.loads((path / f'{example_id}.response.json').read_text())['payload']


def is_advisory_area(
  geometry: Any, *, latitude: tuple[float, float], longitude: tuple[float, float]
) -> None:
  """An aviation outline: a closed polygon, latitude first -- the reverse of every other
  geometry in this API, which the box around the issuing unit's airspace proves."""
  assert geometry['type'] == 'Polygon'
  for ring in geometry['coordinates']:
    assert ring[0] == ring[-1] and len(ring) > 3
    for lat, lon in ring:
      assert latitude[0] < lat < latitude[1]
      assert longitude[0] < lon < longitude[1]


FORT_WORTH = {'latitude': (25.0, 40.0), 'longitude': (-112.0, -88.0)}
"""Fort Worth Center's airspace, generously: north Texas and its neighbours."""
ALASKA = {'latitude': (45.0, 75.0), 'longitude': (-200.0, -125.0)}
"""Alaska, with the Aleutians past the antimeridian: the service does not wrap -190 to 170."""
EAST = {'latitude': (5.0, 50.0), 'longitude': (-100.0, -60.0)}
"""The eastern third of the contiguous US and the waters off it, where the `E` convective
SIGMETs are issued. Miami's oceanic airspace reaches into the Caribbean: the 162 `E` outlines
of 2026-10-06 to 10-13 spanned latitude 12.22 to 44.92 and longitude -93.96 to -67.01."""


def is_newest_first(features: Any) -> None:
  issued = [feature['properties']['issueTime'] for feature in features]
  assert issued == sorted(issued, reverse=True), 'the service answers newest first'


def cwsu(result: Any) -> None:
  """A weather unit is an organization, like an office, without an office's zones."""
  asked = example_request('aviation.get_cwsu', 'seattle')
  assert result['id'] == asked['cwsu_id'] == 'ZSE'
  assert result['name'] == 'Seattle, WA'
  assert result['address']['addressRegion'] == 'WA'
  assert result['nwsRegion'] == 'wr'
  assert 'responsibleForecastZones' not in result


def cwas(result: Any) -> None:
  """The unit's week of advisories, newest first, each named by its date and sequence."""
  asked = example_request('aviation.list_cwas', 'fort_worth')
  features = result['features']
  assert features
  is_newest_first(features)
  for feature in features:
    advisory = feature['properties']
    assert advisory['cwsu'] == asked['cwsu_id']
    assert advisory['sequence'] >= 101
    assert advisory['start'] <= advisory['end']
    issued = advisory['issueTime'].date().isoformat()
    assert advisory['id'].endswith(
      f'/cwsus/{asked["cwsu_id"]}/cwas/{issued}/{advisory["sequence"]}'
    )
    if feature['geometry'] is not None:
      is_advisory_area(feature['geometry'], **FORT_WORTH)


def cwa(result: Any) -> None:
  """The advisory the date and sequence name, whole, and the same one the list holds."""
  asked = example_request('aviation.get_cwa', 'latest')
  advisory = result['properties']
  assert (advisory['cwsu'], advisory['sequence']) == (asked['cwsu_id'], asked['sequence'])
  assert advisory['issueTime'].date().isoformat() == asked['date']
  assert advisory['text'] and advisory['observedProperty']
  is_advisory_area(result['geometry'], **FORT_WORTH)
  listed = recorded_payload('aviation.list_cwas', 'fort_worth')['features']
  assert asked['cwsu_id'] == example_request('aviation.list_cwas', 'fort_worth')['cwsu_id']
  # The list keeps a week. The service answers 500 for most single advisories (see the
  # endpoint's notes), so a re-recording can renew the list and keep an older advisory here;
  # one from inside the list's week must be in it.
  oldest = min(datetime.fromisoformat(feature['properties']['issueTime']) for feature in listed)
  if advisory['issueTime'] >= oldest:
    assert advisory['id'] in {feature['properties']['id'] for feature in listed}


def sigmets_by_sequence(result: Any) -> None:
  """A sequence filter alone reaches back through the whole week: one series, many days."""
  asked = example_request('aviation.list_sigmets', 'convective_1e')
  features = result['features']
  assert features
  is_newest_first(features)
  assert {feature['properties']['sequence'] for feature in features} == {asked['sequence']}
  assert len({feature['properties']['issueTime'].date() for feature in features}) > 1
  for feature in features:
    assert feature['properties']['atsu'] == 'KKCI'
    if feature['geometry'] is not None:
      is_advisory_area(feature['geometry'], **EAST)


def is_sigmet_of(feature: Any, atsu: str) -> Any:
  """A message from `atsu`, named by its UTC issue date and minute: the URL `get_sigmet` takes."""
  sigmet = feature['properties']
  issued = sigmet['issueTime']
  assert sigmet['atsu'] == atsu
  assert sigmet['id'].endswith(f'/sigmets/{atsu}/{issued:%Y-%m-%d}/{issued:%H%M}')
  assert sigmet['start'] <= sigmet['end']
  if feature['geometry'] is not None:
    is_advisory_area(feature['geometry'], **ALASKA)
  return sigmet


def sigmets_for_atsu(result: Any) -> None:
  """One unit's week, newest first."""
  asked = example_request('aviation.list_sigmets_for_atsu', 'anchorage')
  features = result['features']
  assert features
  is_newest_first(features)
  for feature in features:
    is_sigmet_of(feature, asked['atsu'])
  assert len({feature['properties']['issueTime'].date() for feature in features}) > 1


def sigmets_on_date(result: Any) -> None:
  """One unit's day: only that date, and every one of them also in the unit's week."""
  asked = example_request('aviation.list_sigmets_for_atsu_on_date', 'anchorage')
  features = result['features']
  assert features
  is_newest_first(features)
  week = recorded_payload('aviation.list_sigmets_for_atsu', 'anchorage')['features']
  for feature in features:
    sigmet = is_sigmet_of(feature, asked['atsu'])
    assert sigmet['issueTime'].date().isoformat() == asked['date']
    assert sigmet['id'] in {other['properties']['id'] for other in week}


def sigmet(result: Any) -> None:
  """The message the unit, date and minute name, with its area."""
  asked = example_request('aviation.get_sigmet', 'anchorage_latest')
  message = is_sigmet_of(result, asked['atsu'])
  issued = message['issueTime']
  assert (issued.date().isoformat(), f'{issued:%H%M}') == (asked['date'], asked['time'])
  assert result['geometry'] is not None


def one_station(result: Any) -> None:
  """One station, returned whole: the geometry is the only place its coordinates are."""
  asked = example_request('stations.get_station', 'ksea')
  assert result['type'] == 'Feature'
  assert result['id'] == f'https://api.weather.gov/stations/{asked["station_id"]}'
  is_point(result['geometry'])
  longitude, latitude = result['geometry']['coordinates']
  assert round(latitude) == 47 and round(longitude) == -122
  properties = result['properties']
  assert properties['stationIdentifier'] == asked['station_id']
  assert properties['timeZone'] == 'America/Los_Angeles'
  is_measurement(properties['elevation'], unit='wmoUnit:m')
  # The county `zones.list_transmitters` records its transmitters for.
  assert properties['county'].endswith('/zones/county/WAC033')


def observation_at(result: Any) -> None:
  """The observation at exactly the moment asked for, unwrapped like the latest one."""
  asked = example_request('stations.get_observation', 'ksea_metar')
  assert 'properties' not in result
  assert result['stationId'] == asked['station_id']
  assert result['timestamp'] == datetime.fromisoformat(asked['time'])
  # The refresh picks a METAR on purpose: the raw report is the reason to fetch this one.
  assert result['rawMessage'].startswith(f'{asked["station_id"]} ')
  is_measurement(result['temperature'], unit='wmoUnit:degC')


def tafs(result: Any) -> None:
  """A week of forecasts for one airport, newest first, each covering a later span."""
  asked = example_request('stations.list_tafs', 'ksea')
  graph = result['@graph']
  assert len(graph) > 10
  issued = [taf['issueTime'] for taf in graph]
  assert issued == sorted(issued, reverse=True)
  for taf in graph:
    assert taf['location'] == asked['station_id']
    assert taf['id'].startswith(f'https://api.weather.gov/stations/{asked["station_id"]}/tafs/')
    assert taf['issueTime'] <= taf['start'] < taf['end']
  # Well-Known Text, latitude first: the reverse of the station's own GeoJSON coordinates.
  longitude, latitude = recorded_payload('stations.get_station', 'ksea')['geometry']['coordinates']
  first, second = graph[0]['geometry'].removeprefix('POINT(').removesuffix(')').split()
  assert (float(first), float(second)) == (round(latitude, 2), round(longitude, 2))


def active_briefing(result: Any) -> None:
  """An office with a briefing out, and the PDF it points at."""
  asked = example_request('offices.get_briefing', 'active')
  briefing = result['briefing']
  assert briefing is not None
  assert briefing['officeId'] == asked['office_id']
  assert briefing['startTime'] < briefing['endTime']
  assert briefing['download'] == (
    f'https://api.weather.gov/offices/{asked["office_id"]}/briefing/download/{briefing["id"]}'
  )


def no_briefing(result: Any) -> None:
  """Most offices, most days: a 200 and an honest null, not an error."""
  assert result['briefing'] is None


def headlines(result: Any) -> None:
  """An office's headlines, each a link whose HTML repeats its title."""
  asked = example_request('offices.list_headlines', 'wakefield')
  graph = result['@graph']
  assert graph
  for headline in graph:
    assert headline['office'] == f'https://api.weather.gov/offices/{asked["office_id"]}'
    assert headline['@id'] == f'{headline["office"]}/headlines/{headline["id"]}'
    assert headline['title'] in headline['content']
    assert headline['summary'] is None or isinstance(headline['summary'], str)


def one_headline(result: Any) -> None:
  """The headline asked for, the same one the office lists."""
  asked = example_request('offices.get_headline', 'wakefield')
  assert result['id'] == asked['headline_id']
  listed = {
    entry['id']: entry
    for entry in recorded_payload('offices.list_headlines', 'wakefield')['@graph']
  }
  assert listed[result['id']]['title'] == result['title']
  assert listed[result['id']]['link'] == result['link']


def weather_stories(result: Any) -> None:
  """An office's weather stories, each a graphic with its text."""
  asked = example_request('offices.list_weather_stories', 'wakefield')
  stories = result['stories']
  assert stories
  for story in stories:
    assert story['officeId'] == asked['office_id']
    assert story['title'] and story['description']
    assert story['startTime'] < story['endTime']
    assert story['download'] is None or story['download'].startswith(
      f'https://api.weather.gov/offices/{asked["office_id"]}/weatherstories/download/'
    )


def radio_last_page(result: Any) -> None:
  """The last page of every transmitter: short, with no next page, repeats and all."""
  graph = result['@graph']
  assert 0 < len(graph) < 500
  assert 'pagination' not in result
  calls = [transmitter['callSign'] for transmitter in graph]
  # Each transmitter arrives many times over, as it does for a county.
  assert len(set(calls)) < len(calls)
  for transmitter in graph:
    assert transmitter['@id'] == f'https://api.weather.gov/radio/{transmitter["callSign"]}'
    assert len(transmitter['sameCodes']) == len(transmitter['counties'])
    assert 162 < transmitter['transmitterFrequency'] < 163


def one_transmitter(result: Any) -> None:
  """One transmitter by call sign: the one `zones.list_transmitters` found for King County."""
  asked = example_request('radio.get_transmitter', 'seattle')
  assert result['callSign'] == asked['call_sign']
  assert result['@id'] == f'https://api.weather.gov/radio/{asked["call_sign"]}'
  county = next(
    entry
    for entry in recorded_payload('zones.list_transmitters', 'king_county')['@graph']
    if entry['callSign'] == asked['call_sign']
  )
  assert result['counties'] == county['counties']
  assert result['transmitterFrequency'] == Decimal(county['transmitterFrequency'])


def is_interval(interval: str) -> tuple[datetime, timedelta]:
  """The start and length of a `start/duration` ISO 8601 interval, the form the radar
  examples ask in: `2026-09-30T23:00:00Z/PT10M`."""
  start, duration = interval.split('/')
  match = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?', duration)
  assert match, f'{duration} is not an hours-and-minutes duration'
  hours, minutes = (int(part or 0) for part in match.groups())
  length = timedelta(hours=hours, minutes=minutes)
  return datetime.fromisoformat(start.replace('Z', '+00:00')), length


def is_ping_group(group: Any) -> None:
  """A ping group: target name to whether it answered, or `[]` when there are none."""
  if isinstance(group, dict):
    assert all(isinstance(answered, bool) for answered in group.values())
  else:
    assert group == []


def radar_servers(result: Any) -> None:
  """The LDM ingest servers and the two distribution hosts, each with its health. The
  `command` block and the service flags come only with the LDM servers."""
  servers = {server['id']: server for server in result['@graph']}
  assert {'ldm1', 'rds', 'tds'} <= set(servers)
  for name, server in servers.items():
    assert server['@id'].endswith('/radar/servers/' + name)
    assert isinstance(server['collectionTime'], datetime)
    for group in server['ping']['targets'].values():
      is_ping_group(group)
    if server['type'] == 'ldm':
      assert isinstance(server['active'], bool)
      assert isinstance(server['command']['lastExecutedTime'], datetime)
    else:
      assert 'command' not in server and 'active' not in server
  # The service's empty map is `[]`: the reason the ping groups are a union at all.
  assert any(
    group == [] for server in servers.values() for group in server['ping']['targets'].values()
  )
  # The distribution hosts ping no radars, and say so with an empty group.
  assert servers['rds']['ping']['targets']['radar'] == []


def radar_server(result: Any) -> None:
  """One LDM server: its queue spans oldest to newest, and its uptime is a boot time."""
  asked = example_request('radar.get_server', 'ldm1')
  assert result['id'] == asked['server_id'] and result['type'] == 'ldm'
  ldm = result['ldm']
  assert ldm['count'] > 0 and ldm['storageSize'] > 0
  assert ldm['oldestProduct'] <= ldm['latestProduct']
  assert result['hardware']['uptime'] < result['collectionTime']
  assert result['network']['eth0']['interface'] == 'eth0'
  assert isinstance(result['ping']['targets']['radar']['KATX'], bool)


def spgds(result: Any) -> None:
  """One minute of SPG data server reports. Every time in a report but `timestamp` is Unix
  seconds sent as a string; the declared formats turn each into a real `datetime`, and the
  counts into numbers."""
  start, length = is_interval(example_request('radar.list_spgds', 'one_minute')['published'])
  reports = result['@graph']
  assert reports
  for report in reports:
    assert start <= report['timestamp'] <= start + length
    for block in (report['dataflow'], report['connectQ'], report['appRunning']):
      assert isinstance(block['stateSince'], datetime)
      assert block['stateSince'] <= block['stateValid']
    assert isinstance(report['ldm']['conns'], int)
    assert 0 <= report['secondHD']['pctUsed'] <= 100
    assert isinstance(report['throughput']['in'], Decimal)
    assert report['spgdsUpSince']['upSince'] < report['timestamp']
    assert report['spg']
    for site in report['spg'].values():
      assert isinstance(site['ldmPingStateSince'], datetime)
  timestamps = [report['timestamp'] for report in reports]
  assert timestamps == sorted(timestamps, reverse=True)


def radar_profilers(result: Any) -> None:
  """The wind profilers: radars with a place but no Level II feed, so no status and every
  latency field null."""
  asked = example_request('radar.list_stations', 'profilers')
  features = result['features']
  assert features
  for feature in features:
    radar = feature['properties']
    assert radar['stationType'] in asked['stationType']
    assert feature['id'] == radar['@id']
    is_point(feature['geometry'])
    assert radar['rda'] is None
    assert all(value is None for value in radar['latency'].values())
    assert 'performance' not in radar and 'adaptation' not in radar


def radar_two_kinds(result: Any) -> None:
  """Two kinds of radar in one filter, and both kinds back. The service reads
  `stationType=TDWR,Profiler` and keeps only the last of a repeated key, so a client sending
  `stationType=TDWR&stationType=Profiler` would get the profilers alone. The mock expects the
  comma form (`match.query_arrays`), so this also fails if the core stops joining."""
  asked = example_request('radar.list_stations', 'tdwr_and_profilers')
  assert len(asked['stationType']) == 2
  kinds = {feature['properties']['stationType'] for feature in result['features']}
  assert kinds == set(asked['stationType'])


def radar_station(result: Any) -> None:
  """One NEXRAD radar, whole: the feature, its latency in seconds, and the maintenance
  reports only this endpoint sends. Between reports a WSR-88D sends a report as `[]` with a
  null `timestamp`, as a TDWR always does (KATX did on 2026-10-13), so a re-recording may
  catch either."""
  asked = example_request('radar.get_station', 'seattle')
  radar = result['properties']
  assert radar['id'] == asked['station_id'] and radar['stationType'] == 'WSR-88D'
  assert result['id'] == radar['@id']
  is_point(result['geometry'])
  assert radar['latency']['current']['unitCode'] == 'nwsUnit:s'
  assert isinstance(radar['latency']['levelTwoLastReceivedTime'], datetime)
  assert radar['rda']['properties']['volumeCoveragePattern']
  for report in (radar['performance'], radar['adaptation']):
    readings = report['properties']
    if readings == []:
      assert report['timestamp'] is None
      continue
    assert isinstance(readings, dict) and readings
    measured = [r for r in readings.values() if isinstance(r, dict)]
    assert measured and all('unitCode' in r for r in measured)
  performance = radar['performance']['properties']
  if performance:
    assert performance['transmitterPeakPower']['unitCode'] == 'wmoUnit:kW'


def radar_alarms(result: Any) -> None:
  """A radar's alarm log, newest first, every entry about the radar asked for."""
  asked = example_request('radar.list_station_alarms', 'seattle')
  alarms = result['@graph']
  assert alarms
  assert result['@id'].endswith(f'/radar/stations/{asked["station_id"]}/alarms')
  for alarm in alarms:
    assert alarm['stationId'] == asked['station_id']
    assert alarm['message'] and alarm['status']
  timestamps = [alarm['timestamp'] for alarm in alarms]
  assert timestamps == sorted(timestamps, reverse=True)


def radar_queue(result: Any) -> None:
  """The first products into one host's queue from the start of the window: the `limit` keeps
  the oldest, which is why the answer starts at the window's start."""
  asked = example_request('radar.get_queue', 'seattle_capped')
  start, length = is_interval(asked['arrived'])
  products = result['@graph']
  assert len(products) == asked['limit']
  arrivals = [product['arrivalTime'] for product in products]
  assert arrivals == sorted(arrivals)
  for product in products:
    assert product['host'] == asked['host'] and product['stationId'] == asked['station']
    assert start <= product['arrivalTime'] < start + length
    assert product['creationTime'] <= product['arrivalTime']
    assert product['size'] > 0


PROVES: dict[str, Callable[[Any], None]] = {
  'points.get_point[seattle]': point,
  'forecast.get_forecast[seattle]': forecast,
  'forecast.get_hourly_forecast[seattle]': hourly_forecast,
  'forecast.get_grid_data[seattle]': grid_data,
  'stations.list_stations[two_ids]': stations_by_id,
  'stations.list_stations[washington]': stations,
  'stations.get_latest_observation[ksea]': latest_observation,
  'stations.get_observations[ksea_window]': observations,
  'stations.get_observations[ksea_capped]': capped_observations,
  'alerts.get_active_alerts[severe]': active_alerts,
  'alerts.get_alert[one]': one_alert,
  'alerts.list_alerts[first_page]': alert_list,
  'alerts.list_alerts[second_page]': alert_second_page,
  'alerts.get_alert[null_description]': null_description,
  'alerts.get_alert[null_response]': null_response,
  'alerts.count_active_alerts[now]': active_alert_count,
  'alerts.get_active_alerts_for_zone[in_effect]': zone_alerts,
  'alerts.get_active_alerts_for_area[in_effect]': area_alerts,
  'alerts.get_active_alerts_for_region[in_effect]': region_alerts,
  'alerts.list_alert_types[all]': alert_types,
  'offices.get_office[seattle]': office,
  'products.list_product_types[all]': product_types,
  'glossary.list_terms[all]': glossary,
  'zones.list_zones[seattle]': zones_at_point,
  'zones.list_zones[two_ids]': zones_by_id,
  'zones.list_zones[washington_fire]': zones_filtered,
  'zones.list_zones_by_type[washington_counties]': zones_of_type,
  'zones.get_zone[seattle]': zone,
  'zones.get_forecast[seattle]': zone_forecast,
  'zones.list_transmitters[king_county]': transmitters,
  'stations.get_observations_for_zone[seattle_capped]': zone_observations,
  'stations.list_stations_for_zone[seattle]': zone_stations,
  'stations.list_stations_for_gridpoint[seattle_nearest]': gridpoint_stations,
  'aviation.get_cwsu[seattle]': cwsu,
  'aviation.list_cwas[fort_worth]': cwas,
  'aviation.get_cwa[latest]': cwa,
  'aviation.list_sigmets[convective_1e]': sigmets_by_sequence,
  'aviation.list_sigmets_for_atsu[anchorage]': sigmets_for_atsu,
  'aviation.list_sigmets_for_atsu_on_date[anchorage]': sigmets_on_date,
  'aviation.get_sigmet[anchorage_latest]': sigmet,
  'stations.get_station[ksea]': one_station,
  'stations.get_observation[ksea_metar]': observation_at,
  'stations.list_tafs[ksea]': tafs,
  'offices.get_briefing[active]': active_briefing,
  'offices.get_briefing[seattle]': no_briefing,
  'offices.list_headlines[wakefield]': headlines,
  'offices.get_headline[wakefield]': one_headline,
  'offices.list_weather_stories[wakefield]': weather_stories,
  'radio.list_transmitters[last_page]': radio_last_page,
  'radio.get_transmitter[seattle]': one_transmitter,
  'radar.list_servers[all]': radar_servers,
  'radar.get_server[ldm1]': radar_server,
  'radar.list_spgds[one_minute]': spgds,
  'radar.list_stations[profilers]': radar_profilers,
  'radar.list_stations[tdwr_and_profilers]': radar_two_kinds,
  'radar.get_station[seattle]': radar_station,
  'radar.list_station_alarms[seattle]': radar_alarms,
  'radar.get_queue[seattle_capped]': radar_queue,
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


def frozen_examples() -> list[str]:
  """The request halves `recapture.sh` does not re-record, from `frozen_examples.txt`."""
  lines = (Path(__file__).parent / 'frozen_examples.txt').read_text().splitlines()
  return [line for line in lines if line and not line.startswith('#')]


def test_frozen_examples_are_recorded_requests():
  """A frozen example is never re-recorded, so its recording must already be here, and a
  typo in the list would silently re-record nothing less."""
  frozen = frozen_examples()
  assert frozen == ['spec/endpoints/alerts/get_alert/examples/null_response.request.json']
  for path in frozen:
    assert (PROJECT / path).is_file(), path
    assert (PROJECT / path.replace('.request.json', '.response.json')).is_file(), path


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
