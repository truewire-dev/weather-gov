"""The hand-written core, tested directly.

Everything here is what the generator does not write: the `User-Agent` the service asks
for, the envelope, the error mapping, and how a list-valued filter and a `:` in a path
reach the wire. The mock server is the wire.
"""

import json
from pathlib import Path

import pytest
from truewire_core.exceptions import ApiError, BadRequest

from weather_gov.core import raise_for_status, unwrap, user_agent

PROJECT = Path(__file__).resolve().parents[3]


class TestUserAgent:
  """The service asks every caller to identify itself, and can block one that does not."""

  def test_the_contact_is_in_the_user_agent(self):
    assert 'hello@example.com' in user_agent('hello@example.com')

  def test_the_client_is_named_too(self):
    """So a rate-limit conversation can start with 'your truewire client is doing X'."""
    assert user_agent('hello@example.com').startswith('truewire-weather-gov')

  def test_contact_has_no_default(self):
    """A default would be a lie about who is calling, so `new()` requires one."""
    from weather_gov import Weather

    with pytest.raises(TypeError):
      Weather.new()  # type: ignore[call-arg]


class TestUnwrap:
  """An endpoint that declares an envelope gets the payload; one that does not gets it all."""

  def test_no_declared_payload_returns_the_body(self):
    body = {'type': 'Feature', 'properties': {'gridId': 'SEW'}}
    assert unwrap(body, None) is body

  def test_a_declared_payload_is_read_out(self):
    assert unwrap({'properties': {'gridId': 'SEW'}}, 'properties') == {'gridId': 'SEW'}

  def test_a_dotted_payload_walks(self):
    assert unwrap({'a': {'b': 7}}, 'a.b') == 7

  def test_a_missing_payload_raises_rather_than_returning_none(self):
    """The failure a caller wants is 'the wire shape changed', not a validation error
    against `None` three frames later."""
    with pytest.raises(ApiError, match='no `properties` to unwrap'):
      unwrap({'type': 'Feature'}, 'properties')


class TestErrors:
  """The service answers errors in RFC 7807, and names the bad parameter when there is one."""

  def test_a_parameter_error_names_the_parameter_and_why(self):
    body = (
      '{"parameterErrors": [{"parameter": "query.severity[0]", "message": '
      '"Does not have a value in the enumeration [\\"Extreme\\",\\"Severe\\"]"}], '
      '"title": "Bad Request", "status": 400}'
    )
    with pytest.raises(BadRequest) as caught:
      raise_for_status('GET', '/alerts/active', 400, body)
    assert 'query.severity[0]' in str(caught.value)
    assert 'enumeration' in str(caught.value)

  def test_a_400_without_parameter_errors_falls_back_to_the_detail(self):
    with pytest.raises(BadRequest, match='Bad Request'):
      raise_for_status('GET', '/points/1,2', 400, '{"detail": "Bad Request", "status": 400}')

  def test_a_non_json_body_still_produces_a_useful_message(self):
    with pytest.raises(ApiError, match='<html>'):
      raise_for_status('GET', '/points/1,2', 502, '<html>gateway</html>')

  def test_the_status_and_the_path_are_in_every_message(self):
    with pytest.raises(ApiError, match=r'GET /offices/SEW: HTTP 503'):
      raise_for_status('GET', '/offices/SEW', 503, '')


class TestOnTheWire:
  """Through the mock server, so the URL the client builds is the URL that is matched."""

  @pytest.mark.asyncio
  async def test_a_repeated_filter_travels_as_repeated_keys(self, client):
    """`state=['WA']` has to reach the wire as `?state=WA`, not as `?state=%5B'WA'%5D`.
    The mock matches the recorded query exactly, so a wrong rendering 422s here."""
    page = await client.stations.list_stations(state=['WA'], limit=20)
    assert len(page['features']) == 20

  @pytest.mark.asyncio
  async def test_a_colon_in_a_path_is_not_percent_encoded(self, client):
    """An alert id is `urn:oid:...`, and `:` is a legal path character. Encoding it would
    send a URL the service never printed."""
    alert_id = json.loads(
      (PROJECT / 'spec/endpoints/alerts/get_alert/examples/one.request.json').read_text()
    )['request']['id']
    assert ':' in alert_id
    alert = await client.alerts.get_alert(alert_id)
    assert alert['properties']['id'] == alert_id

  @pytest.mark.asyncio
  async def test_an_enveloped_endpoint_returns_the_payload_not_the_wrapper(self, client):
    """The whole point of the envelope: `.gridId`, not `.properties.gridId`."""
    point = await client.points.get_point(latitude=47.6062, longitude=-122.3321)
    assert point['gridId'] == 'SEW'
    assert 'properties' not in point

  @pytest.mark.asyncio
  async def test_an_endpoint_without_an_envelope_returns_the_whole_feature(self, client):
    """An alert's geometry is real data, so that one is not unwrapped."""
    page = await client.alerts.get_active_alerts(status=['actual'], severity=['Severe'])
    assert page['type'] == 'FeatureCollection'
    assert page['features'][0]['properties']['severity'] == 'Severe'
