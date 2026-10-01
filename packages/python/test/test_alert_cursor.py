"""Run the documented loop through the generated client and inspect HTTP parameters."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from truewire_core.http import HttpClient

from weather_gov import Weather

PROJECT = Path(__file__).resolve().parents[3]


@pytest.mark.asyncio
@pytest.mark.parametrize('termination', ['empty', 'missing_pagination', 'missing_cursor'])
async def test_documented_cursor_walk_preserves_filters(monkeypatch, termination):
  page = json.loads(
    (PROJECT / 'spec/endpoints/alerts/list_alerts/examples/first_page.response.json').read_text()
  )['payload']
  row = page['features'][0]
  seen = []

  async def request(self, method, url, **kwargs):
    wire = httpx.Request(method, url, params=kwargs['params'])
    query = parse_qs(wire.url.query.decode())
    seen.append(query)
    assert query['start'] == ['2026-09-29T00:00:00Z']
    assert query['end'] == ['2026-09-29T06:00:00Z']
    assert query['status'] == ['actual']
    assert query['limit'] == ['100']
    index = len(seen) - 1
    assert index < 3, 'the empty page must terminate even if it carries a next link'
    if index:
      assert query['cursor'] == [f'page{index}+/=']
    else:
      assert 'cursor' not in query
    result = {
      'type': 'FeatureCollection',
      'features': [row] * [100, 76, 0][index],
      'pagination': {'next': f'https://api.weather.gov/alerts?cursor=page{index + 1}%2B%2F%3D'},
    }
    if index == 1 and termination == 'missing_pagination':
      del result['pagination']
    elif index == 1 and termination == 'missing_cursor':
      result['pagination'] = {'next': 'https://api.weather.gov/alerts?limit=100'}
    return httpx.Response(200, json=result, request=wire)

  monkeypatch.setattr(HttpClient, 'request', request)
  source = (PROJECT / 'docs/how-to/walk-alerts.md').read_text()
  block = re.search(r'```python\n(.*?)```', source, re.S)
  assert block is not None
  namespace = {}
  exec(compile(block[1], 'docs/how-to/walk-alerts.md', 'exec'), namespace)
  async with Weather.new(contact='tests@truewire.dev') as client:
    rows = [
      row
      async for row in namespace['walk_alerts'](
        client,
        start=datetime(2026, 9, 29, tzinfo=timezone.utc),
        end=datetime(2026, 9, 29, 6, tzinfo=timezone.utc),
      )
    ]
  assert len(rows) == 176
  assert len(seen) == (3 if termination == 'empty' else 2)
