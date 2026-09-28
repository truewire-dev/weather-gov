"""The declared `seek` walk, against the mock.

`stations.get_observations` pages by time: the walk moves `end` back to the oldest
observation of each page that came back full (ADR 0013). The algorithm is the toolchain's
and its own suite covers it; what is worth testing here is what the declaration buys a
caller on this service's real responses:

1. a span under the cap is one request, and the walk does not wander past it;
2. a capped page is progress rather than the whole span: the next request ends at the
   oldest observation the capped page held, which is only right because the service keeps
   the newest rows when it caps (the declared `anchor: end`);
3. the observation on the boundary, which the next request re-reads, is dropped by its
   timestamp rather than yielded twice.

Both are real recordings of the same six hours at KSEA: one under the cap, one asked for
with `limit=10` so the page comes back full.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[3]
EXAMPLES = PROJECT / 'spec/endpoints/stations/get_observations/examples'


def recorded(example: str) -> dict:
  """The request half of one recorded example, which is the source of truth for the walk.

  Read rather than written here: the service keeps about a week of observations, so
  `test/refresh_examples.py` moves both windows forward before every re-recording. A
  constant would turn that repair into a test failure -- which is exactly what it did the
  first time these tests were written.
  """
  return json.loads((EXAMPLES / f'{example}.request.json').read_text())['request']


def observations(example: str) -> list[dict]:
  return json.loads((EXAMPLES / f'{example}.response.json').read_text())['payload']['features']


def instant(value: str) -> datetime:
  return datetime.fromisoformat(value.replace('Z', '+00:00'))


WINDOW = recorded('ksea_window')
CAPPED = recorded('ksea_capped')
START = instant(WINDOW['start'])
END = instant(WINDOW['end'])
CAP = CAPPED['limit']

ROWS = observations('ksea_window')
"""What the six hours actually hold. Moves with every re-recording; what does not move is
that it is under the service's cap, which is why that walk is one page."""


class TestASpanUnderTheCap:
  @pytest.mark.asyncio
  async def test_is_one_page(self, client):
    """Under the service's cap, so the walk is done in one request. The mock holds one
    exchange for this span, and a second request would 422 rather than quietly return
    nothing."""
    assert len(ROWS) < 500, 'this span is meant to sit under the cap, so the walk is one page'
    walk = client.stations.get_observations_paged('KSEA', start=START, end=END, limit=500)
    pages = [page async for page in walk.pages()]
    assert len(pages) == 1
    assert pages[0].next is None
    assert len(pages[0].rows) == len(ROWS)

  @pytest.mark.asyncio
  async def test_awaiting_it_returns_every_observation_newest_first(self, client):
    rows = await client.stations.get_observations_paged('KSEA', start=START, end=END, limit=500)
    assert [row['id'] for row in rows] == [row['id'] for row in ROWS]


class TestACappedPage:
  """The defect the walk exists for, on a real response.

  The service answers a span wider than its cap with the newest `limit` rows and says
  nothing about the ones it withheld. A walk that took that page as the whole span would
  leave a gap in a time series with no error anywhere.
  """

  @pytest.mark.asyncio
  async def test_keeps_the_newest_rows(self):
    """The recorded fact `anchor: end` rests on: the capped page is the head of the full
    one, not some other slice of it."""
    capped = observations('ksea_capped')
    assert CAPPED['start'] == WINDOW['start'] and CAPPED['end'] == WINDOW['end']
    assert len(capped) == CAP < len(ROWS)
    assert [row['id'] for row in capped] == [row['id'] for row in ROWS[:CAP]]

  @pytest.mark.asyncio
  async def test_moves_end_to_the_oldest_observation_it_held(self, client):
    """Ten rows asked for, ten returned: the span held more, so the walk continues from the
    oldest of them, and `start` stays the caller's."""
    walk = client.stations.get_observations_paged('KSEA', start=START, end=END, limit=CAP)
    rows, following = await walk.next(walk.init)
    assert len(rows) == CAP
    assert following is not None
    pos, carried = following
    oldest = observations('ksea_capped')[-1]
    assert pos == instant(oldest['properties']['timestamp'])
    assert [row['id'] for row in carried] == [oldest['id']]


class TestTheBoundary:
  @pytest.mark.asyncio
  async def test_the_re_read_observation_is_not_yielded_twice(self, client):
    """Both bounds are inclusive, so the request after a capped page re-reads the
    observation it ended on. Resumed as if a previous page had already yielded the newest
    observation of the span, the walk drops it by timestamp and yields the rest."""
    walk = client.stations.get_observations_paged('KSEA', start=START, end=END, limit=500)
    rows, following = await walk.next((END, [ROWS[0]]))
    assert following is None
    assert [row['id'] for row in rows] == [row['id'] for row in ROWS[1:]]
