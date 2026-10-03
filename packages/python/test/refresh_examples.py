#!/usr/bin/env python3
"""Repoint the examples that go stale on their own, before anything is captured.

Most of this API is stable enough to re-record from a fixed request: the Seattle grid cell
will still be the Seattle grid cell next week. Two kinds are not:

- `stations.get_observations` names a six-hour window. The service keeps about a week of
  observations and then drops them, so last month's window records as an empty
  `FeatureCollection` -- a 200 with nothing in it, which records exactly as happily as a
  full one and turns the recording into a file that proves nothing. Both observation
  examples are repointed to the same window so the capped one stays a comparison, and
  `stations.get_observations_for_zone` moves with them, since it reads the same week.
- `alerts.get_alert` names one alert by identifier. Alerts expire, usually within hours,
  and the identifier is then gone. The replacement is read from whatever is severe and in
  effect right now -- the same query `alerts.get_active_alerts` records.
- `stations.get_observation` names one observation by its exact timestamp, which ages out
  with the rest of the week. It is repointed to the newest METAR in the same settled
  window the observation examples read.
- `offices.get_headline` names one headline by id, and an office retires its headlines. It
  is repointed to the first one the office lists now.
- `offices.get_briefing`'s `active` example needs an office with a briefing out, and most
  offices have none on most days. It keeps its office while that one has one, and moves to
  the first office that does otherwise.
- `radio.list_transmitters` records the last page, the smallest, and its cursor moves if
  the transmitter list does. A cursor past the end records an empty `@graph` with a 200.

Run before `truewire capture`, not after a capture failed: only one of these fails loudly.

The request half of each example is the source of truth for re-recording, so this edits
that half and leaves the description alone.
"""

import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]

CONTACT = 'hello@truewire.dev'
"""What this script identifies itself as. It does not go through the generated client --
it runs before the client has anything current to record -- so it repeats the same
`User-Agent` policy the core implements."""

OBSERVATIONS = (
  PROJECT / 'spec/endpoints/stations/get_observations/examples',
  PROJECT / 'spec/endpoints/stations/get_observations_for_zone/examples',
)
ALERT = PROJECT / 'spec/endpoints/alerts/get_alert/examples/one.request.json'

ACTIVE = 'https://api.weather.gov/alerts/active?status=actual&severity=Severe'
"""The same query `alerts.get_active_alerts` records, so the alert picked here is one that
recording also holds."""

OBSERVATION = PROJECT / 'spec/endpoints/stations/get_observation/examples/ksea_metar.request.json'
HEADLINE = PROJECT / 'spec/endpoints/offices/get_headline/examples/wakefield.request.json'
BRIEFING = PROJECT / 'spec/endpoints/offices/get_briefing/examples/active.request.json'
RADIO = PROJECT / 'spec/endpoints/radio/list_transmitters/examples/last_page.request.json'

API = 'https://api.weather.gov'

RADIO_PAGE = 500
"""Rows on every page of `/radio` but the last, measured; the service takes no `limit`."""


def fetch(url: str) -> dict:
  request = urllib.request.Request(
    url,
    headers={
      'Accept': 'application/geo+json',
      'User-Agent': f'truewire-weather-gov ({CONTACT})',
    },
  )
  with urllib.request.urlopen(request, timeout=30) as response:
    return json.load(response)


def rewrite(path: Path, changes: dict) -> None:
  document = json.loads(path.read_text())
  document['request'].update(changes)
  path.write_text(json.dumps(document, indent=2) + '\n')
  print(f'{path.relative_to(PROJECT)}: {changes}')


STAMP = '%Y-%m-%dT%H:%M:%SZ'


def settled_window() -> tuple[str, str]:
  """The most recent whole six hours that has settled, as `start` and `end`.

  Ending six hours ago rather than now: the newest observations are still arriving, so a
  window ending at `now` would record a different row count every run for no reason.
  """
  end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=6)
  start = end - timedelta(hours=6)
  return start.strftime(STAMP), end.strftime(STAMP)


def request_of(path: Path) -> dict:
  return json.loads(path.read_text())['request']


def refresh_observations() -> None:
  """Move every observation window to the settled window."""
  start, end = settled_window()
  for request in sorted(
    path for examples in OBSERVATIONS for path in examples.glob('*.request.json')
  ):
    rewrite(request, {'start': start, 'end': end})


def refresh_observation_time() -> None:
  """Point the single-observation example at the newest METAR in the settled window.

  A METAR rather than any observation, because only a METAR carries `rawMessage`, and the
  recording is worth more for holding one.
  """
  start, end = settled_window()
  station = request_of(OBSERVATION)['station_id']
  query = urllib.parse.urlencode({'start': start, 'end': end})
  features = fetch(f'{API}/stations/{station}/observations?{query}')['features']
  metars = [feature for feature in features if feature['properties'].get('rawMessage')]
  if not metars:
    raise SystemExit(f'{station} reported no METAR between {start} and {end}')
  taken = datetime.fromisoformat(metars[0]['properties']['timestamp'])
  rewrite(OBSERVATION, {'time': taken.astimezone(timezone.utc).strftime(STAMP)})


def refresh_headline() -> None:
  """Point the single-headline example at the first headline its office lists now."""
  office = request_of(HEADLINE)['office_id']
  headlines = fetch(f'{API}/offices/{office}/headlines')['@graph']
  if not headlines:
    raise SystemExit(f'{office} lists no headlines, so there is none to fetch by id')
  rewrite(HEADLINE, {'headline_id': headlines[0]['id']})


def refresh_briefing() -> None:
  """Keep the `active` briefing example on an office that has a briefing out."""
  office = request_of(BRIEFING)['office_id']
  if fetch(f'{API}/offices/{office}/briefing')['briefing'] is not None:
    return
  for candidate in sorted(fetch(f'{API}/products/types/AFD/locations')['locations']):
    if fetch(f'{API}/offices/{candidate}/briefing')['briefing'] is not None:
      rewrite(BRIEFING, {'office_id': candidate})
      return
  raise SystemExit('no office has a briefing out right now')


def radio_cursor(row: int) -> str:
  """The cursor of the `/radio` page starting at `row`.

  The service's cursor is base64 JSON naming the first row, `{"i":500}` for the second
  page; it hands that back only inside `pagination.next`, as a whole URL. The encoding is
  not documented, so if it changes this raises rather than recording a wrong page.
  """
  return base64.b64encode(json.dumps({'i': row}, separators=(',', ':')).encode()).decode()


def radio_page(row: int) -> dict:
  cursor = urllib.parse.quote(radio_cursor(row), safe='')
  return fetch(f'{API}/radio?cursor={cursor}')


def refresh_radio() -> None:
  """Point the radio example at the last page of `/radio`: the one with rows and no `next`.

  Found by bisection over page starts, a handful of requests rather than walking all
  hundred-odd pages. A page is past the end when its `@graph` is empty.
  """
  low, high = 0, RADIO_PAGE
  while radio_page(high)['@graph']:
    low, high = high, high * 2
  while high - low > RADIO_PAGE:
    middle = (low + high) // 2 // RADIO_PAGE * RADIO_PAGE
    if radio_page(middle)['@graph']:
      low = middle
    else:
      high = middle
  last = radio_page(low)
  if (last.get('pagination') or {}).get('next'):
    raise SystemExit(f'the /radio page at row {low} names a next page; the cursor encoding moved')
  rewrite(RADIO, {'cursor': radio_cursor(low)})


def refresh_alert() -> None:
  """Point the single-alert example at one that is in effect now."""
  alerts = fetch(ACTIVE)['features']
  if not alerts:
    raise SystemExit(
      'no severe alert is in effect anywhere in the country right now, so there is none '
      'to fetch by identifier; the existing example keeps its identifier and will record '
      'the 404 the service answers for an expired alert'
    )
  rewrite(ALERT, {'id': alerts[0]['properties']['id']})


def main() -> int:
  failed = []
  for step in (
    refresh_observations,
    refresh_alert,
    refresh_observation_time,
    refresh_headline,
    refresh_briefing,
    refresh_radio,
  ):
    try:
      step()
    except (urllib.error.URLError, SystemExit, KeyError, IndexError) as error:
      # One stale example does not stop the other from being repaired, and neither stops
      # the nine examples that need no repair at all from recording.
      print(f'{step.__name__}: {error}', file=sys.stderr)
      failed.append(step.__name__)
  return 1 if failed else 0


if __name__ == '__main__':
  raise SystemExit(main())
