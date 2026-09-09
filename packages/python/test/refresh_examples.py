#!/usr/bin/env python3
"""Repoint the two examples that go stale on their own, before anything is captured.

Most of this API is stable enough to re-record from a fixed request: the Seattle grid cell
will still be the Seattle grid cell next week. Two examples are not:

- `stations.get_observations` names a six-hour window. The service keeps about a week of
  observations and then drops them, so last month's window records as an empty
  `FeatureCollection` -- a 200 with nothing in it, which records exactly as happily as a
  full one and turns the recording into a file that proves nothing. Both observation
  examples are repointed to the same window so the capped one stays a comparison.
- `alerts.get_alert` names one alert by identifier. Alerts expire, usually within hours,
  and the identifier is then gone. The replacement is read from whatever is severe and in
  effect right now -- the same query `alerts.get_active_alerts` records.

Run before `truewire capture`, not after a capture failed: only one of these fails loudly.

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

OBSERVATIONS = PROJECT / 'spec/endpoints/stations/get_observations/examples'
ALERT = PROJECT / 'spec/endpoints/alerts/get_alert/examples/one.request.json'

ACTIVE = 'https://api.weather.gov/alerts/active?status=actual&severity=Severe'
"""The same query `alerts.get_active_alerts` records, so the alert picked here is one that
recording also holds."""


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
  """Move both observation windows to the most recent whole six hours that has settled.

  Ending six hours ago rather than now: the newest observations are still arriving, so a
  window ending at `now` would record a different row count every run for no reason.
  """
  end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=6)
  start = end - timedelta(hours=6)
  stamp = '%Y-%m-%dT%H:%M:%SZ'
  for request in sorted(OBSERVATIONS.glob('*.request.json')):
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


def main() -> int:
  failed = []
  for step in (refresh_observations, refresh_alert):
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
