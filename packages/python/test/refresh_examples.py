#!/usr/bin/env python3
"""Repoint the examples that go stale on their own, before anything is captured.

Most of this API is stable enough to re-record from a fixed request: the Seattle grid cell
will still be the Seattle grid cell next week. Three kinds are not:

- `stations.get_observations` names a six-hour window. The service keeps about a week of
  observations and then drops them, so last month's window records as an empty
  `FeatureCollection` -- a 200 with nothing in it, which records exactly as happily as a
  full one and turns the recording into a file that proves nothing. Both observation
  examples are repointed to the same window so the capped one stays a comparison, and
  `stations.get_observations_for_zone` moves with them, since it reads the same week.
- `alerts.get_alert` names one alert by identifier. Alerts expire, usually within hours,
  and the identifier is then gone. The replacement is read from whatever is severe and in
  effect right now -- the same query `alerts.get_active_alerts` records.
- `aviation.get_cwa`, `aviation.get_sigmet` and `aviation.list_sigmets_for_atsu_on_date`
  name a day. The service keeps about a week of advisories, and an expired one answers 500
  rather than 404. Each is repointed to the newest message with an outline from the unit its list example
  records, so the one recording is also found in the other.

Run before `truewire capture`, not after a capture failed: not all of these fail loudly.

The request half of each example is the source of truth for re-recording, so this edits
that half and leaves the description alone.
"""

import json
import sys
import urllib.error
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

AVIATION = PROJECT / 'spec/endpoints/aviation'
CWAS = AVIATION / 'list_cwas/examples/fort_worth.request.json'
CWA = AVIATION / 'get_cwa/examples/latest.request.json'
SIGMETS = AVIATION / 'list_sigmets_for_atsu/examples/anchorage.request.json'
SIGMETS_ON_DATE = AVIATION / 'list_sigmets_for_atsu_on_date/examples/anchorage.request.json'
SIGMET = AVIATION / 'get_sigmet/examples/anchorage_latest.request.json'


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


def refresh_observations() -> None:
  """Move every observation window to the most recent whole six hours that has settled.

  Ending six hours ago rather than now: the newest observations are still arriving, so a
  window ending at `now` would record a different row count every run for no reason.
  """
  end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=6)
  start = end - timedelta(hours=6)
  stamp = '%Y-%m-%dT%H:%M:%SZ'
  for request in sorted(
    path for examples in OBSERVATIONS for path in examples.glob('*.request.json')
  ):
    rewrite(request, {'start': start.strftime(stamp), 'end': end.strftime(stamp)})


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


def newest_with_area(url: str, what: str) -> dict:
  """The newest feature at `url` that has an outline: the point of fetching one alone."""
  for feature in fetch(url)['features']:
    if feature['geometry'] is not None:
      return feature['properties']
  raise SystemExit(f'{what} has issued nothing with an outline this week')


def refresh_cwa() -> None:
  """Point the single-advisory example at the newest one its unit's list holds."""
  cwsu = json.loads(CWAS.read_text())['request']['cwsu_id']
  advisory = newest_with_area(f'https://api.weather.gov/aviation/cwsus/{cwsu}/cwas', f'CWSU {cwsu}')
  issued = datetime.fromisoformat(advisory['issueTime'])
  rewrite(CWA, {'cwsu_id': cwsu, 'date': f'{issued:%Y-%m-%d}', 'sequence': advisory['sequence']})


def refresh_sigmet() -> None:
  """Point the one-day and the single-message examples at the unit's newest message."""
  atsu = json.loads(SIGMETS.read_text())['request']['atsu']
  sigmet = newest_with_area(f'https://api.weather.gov/aviation/sigmets/{atsu}', f'ATSU {atsu}')
  issued = datetime.fromisoformat(sigmet['issueTime'])
  rewrite(SIGMETS_ON_DATE, {'atsu': atsu, 'date': f'{issued:%Y-%m-%d}'})
  rewrite(SIGMET, {'atsu': atsu, 'date': f'{issued:%Y-%m-%d}', 'time': f'{issued:%H%M}'})


def main() -> int:
  failed = []
  for step in (refresh_observations, refresh_alert, refresh_cwa, refresh_sigmet):
    try:
      step()
    except (urllib.error.URLError, SystemExit, KeyError, IndexError) as error:
      # One stale example does not stop the other from being repaired, and neither stops
      # the examples that need no repair at all from recording.
      print(f'{step.__name__}: {error}', file=sys.stderr)
      failed.append(step.__name__)
  return 1 if failed else 0


if __name__ == '__main__':
  raise SystemExit(main())
