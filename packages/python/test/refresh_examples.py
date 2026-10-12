#!/usr/bin/env python3
"""Repoint the examples that go stale on their own, before anything is captured.

Most of this API is stable enough to re-record from a fixed request: the Seattle grid cell
will still be the Seattle grid cell next week. These examples are not:

- `stations.get_observations` names a six-hour window. The service keeps about a week of
  observations and then drops them, so last month's window records as an empty
  `FeatureCollection` -- a 200 with nothing in it, which records exactly as happily as a
  full one and turns the recording into a file that proves nothing. Both observation
  examples are repointed to the same window so the capped one stays a comparison, and
  `stations.get_observations_for_zone` moves with them, since it reads the same week.
- `radar.list_spgds` and `radar.get_queue` name an interval (`published`, `arrived`), and
  the service keeps about a week of either: a window older than that records an empty
  `@graph`. Both move to the same hour of yesterday, which has long since settled.
- `alerts.get_alert` names one alert by identifier. Alerts expire, usually within hours,
  and the identifier is then gone. The replacement is read from whatever is severe and in
  effect right now -- the same query `alerts.get_active_alerts` records.
- `alerts.list_alerts` names a six-hour window, and the service keeps about a week of
  alerts. It moves with the observation window. Its `second_page` example carries the
  cursor the first page answers, which expires with the window, so it is re-read from the
  service for the moved window.
- `alerts.get_alert`'s `null_description` names an alert whose description is an explicit
  null. The replacement is the newest alert in the service's week that still has one.
- `alerts.get_active_alerts_for_zone`, `_for_area` and `_for_region` name a place. Once its
  alerts expire the place records an empty collection. Each keeps its place while
  `/alerts/active/count` still counts an alert there, and otherwise moves to the place with
  the fewest, which keeps the recording small.

Run before `truewire capture`, not after a capture failed: only one of these fails loudly.

Some examples cannot be repointed, because what they prove may not exist in the service's
week at all. Those are listed in `frozen_examples.txt` and are not re-recorded.

The request half of each example is the source of truth for re-recording, so this edits
that half and leaves the description alone.
"""

import json
import sys
import time
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
RADAR = PROJECT / 'spec/endpoints/radar'
RADAR_WINDOWS = {
  RADAR / 'list_spgds/examples/one_minute.request.json': ('published', 'PT1M'),
  RADAR / 'get_queue/examples/seattle_capped.request.json': ('arrived', 'PT10M'),
}
"""Each radar example with an interval, the parameter holding it, and how long it stays."""

ALERT_WINDOW = PROJECT / 'spec/endpoints/alerts/list_alerts/examples/first_page.request.json'
SECOND_PAGE = PROJECT / 'spec/endpoints/alerts/list_alerts/examples/second_page.request.json'
NULL_DESCRIPTION = (
  PROJECT / 'spec/endpoints/alerts/get_alert/examples/null_description.request.json'
)
PLACES = {
  'zone_id': ('zones', PROJECT / 'spec/endpoints/alerts/get_active_alerts_for_zone/examples'),
  'area': ('areas', PROJECT / 'spec/endpoints/alerts/get_active_alerts_for_area/examples'),
  'region': ('regions', PROJECT / 'spec/endpoints/alerts/get_active_alerts_for_region/examples'),
}
"""Each place parameter, the `/alerts/active/count` map that counts it, and its examples."""

ACTIVE = 'https://api.weather.gov/alerts/active?status=actual&severity=Severe'
"""The same query `alerts.get_active_alerts` records, so the alert picked here is one that
recording also holds."""

COUNT = 'https://api.weather.gov/alerts/active/count'

ALERTS = 'https://api.weather.gov/alerts'

NULL_SEARCH_PAGES = 30
"""How many pages of 500 alerts the null search reads, newest first, before giving up. The
service's week is about 25 pages."""

ATTEMPTS = 4
"""How many times one request is sent. The service answers a few percent of requests with a
500 that the same request, sent again, answers with a 200."""


def fetch(url: str) -> dict:
  request = urllib.request.Request(
    url,
    headers={
      'Accept': 'application/geo+json',
      'User-Agent': f'truewire-weather-gov ({CONTACT})',
    },
  )
  for attempt in range(1, ATTEMPTS + 1):
    try:
      with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)
    except urllib.error.HTTPError as error:
      if error.code < 500 or attempt == ATTEMPTS:
        raise
      time.sleep(2 * attempt)
  raise AssertionError('unreachable')


def alerts_query(request: dict) -> str:
  """An example request of `alerts.list_alerts` as the query string the service reads.

  List filters travel as one comma-separated item, as the generated client sends them.
  """
  return urllib.parse.urlencode(
    {key: ','.join(value) if isinstance(value, list) else value for key, value in request.items()}
  )


def rewrite(path: Path, changes: dict) -> None:
  document = json.loads(path.read_text())
  document['request'].update(changes)
  path.write_text(json.dumps(document, indent=2) + '\n')
  print(f'{path.relative_to(PROJECT)}: {changes}')


def settled_window() -> dict:
  """The most recent whole six hours that has settled.

  Ending six hours ago rather than now: the newest rows are still arriving, so a window
  ending at `now` would record a different row count every run for no reason.
  """
  end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=6)
  start = end - timedelta(hours=6)
  stamp = '%Y-%m-%dT%H:%M:%SZ'
  return {'start': start.strftime(stamp), 'end': end.strftime(stamp)}


def refresh_observations() -> None:
  """Move every observation window to the same settled six hours."""
  window = settled_window()
  for request in sorted(
    path for examples in OBSERVATIONS for path in examples.glob('*.request.json')
  ):
    rewrite(request, window)


def refresh_alert_window() -> None:
  """Move the alert list's window to the settled six hours."""
  rewrite(ALERT_WINDOW, settled_window())


def refresh_second_page() -> None:
  """Point the second page at the cursor the first page answers now.

  Read from the first page's request rather than from the window this run computed, so the
  two stay a pair even when moving the window failed.
  """
  first = json.loads(ALERT_WINDOW.read_text())['request']
  following = fetch(f'{ALERTS}?{alerts_query(first)}').get('pagination', {}).get('next')
  if not following:
    raise SystemExit(f'the first page of {first} has no next page, so there is no cursor')
  (cursor,) = urllib.parse.parse_qs(urllib.parse.urlsplit(following).query)['cursor']
  rewrite(SECOND_PAGE, {**first, 'cursor': cursor})


def refresh_null_description() -> None:
  """Point the null-description example at the newest alert that has one."""
  url = f'{ALERTS}?limit=500'
  for _ in range(NULL_SEARCH_PAGES):
    page = fetch(url)
    for alert in page['features']:
      if alert['properties'].get('description', '') is None:
        rewrite(NULL_DESCRIPTION, {'id': alert['properties']['id']})
        return
    url = page.get('pagination', {}).get('next')
    if not page['features'] or not url:
      break
  raise SystemExit(
    "no alert in the service's week has a null description; the existing example keeps "
    'its identifier and will record the 404 the service answers for an expired alert'
  )


def refresh_alert_places() -> None:
  """Point each place example at a place with an alert in effect now."""
  counts = fetch(COUNT)
  for parameter, (key, examples) in PLACES.items():
    counted = counts[key]
    if parameter == 'zone_id':
      # Forecast zones, not counties: a county's alerts need not name the county.
      counted = {code: n for code, n in counted.items() if code[2] == 'Z'}
    if not counted:
      raise SystemExit(f'no alert is in effect in any of the {key}')
    for request in sorted(examples.glob('*.request.json')):
      current = json.loads(request.read_text())['request'][parameter]
      if current not in counted:
        rewrite(request, {parameter: min(counted, key=lambda code: (counted[code], code))})


def refresh_radar_windows() -> None:
  """Move each radar interval to start on the hour, a day ago, keeping its length."""
  start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(days=1)
  for request, (parameter, duration) in RADAR_WINDOWS.items():
    rewrite(request, {parameter: f'{start:%Y-%m-%dT%H:%M:%SZ}/{duration}'})


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
    refresh_radar_windows,
    refresh_alert,
    refresh_alert_window,
    refresh_second_page,
    refresh_null_description,
    refresh_alert_places,
  ):
    try:
      step()
    except (urllib.error.URLError, SystemExit, KeyError, IndexError, ValueError) as error:
      # One stale example does not stop the others from being repaired, and none stops the
      # examples that need no repair at all from recording.
      print(f'{step.__name__}: {error}', file=sys.stderr)
      failed.append(step.__name__)
  return 1 if failed else 0


if __name__ == '__main__':
  raise SystemExit(main())
