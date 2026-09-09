"""The declared `window` walk, against the mock.

`stations.get_observations` is the reason this project exists as the second showcase: it
is the first recorded, tested use of `window` pagination anywhere in Truewire. The walk
itself is arithmetic on the request bounds, so what is worth testing is not that it
divides correctly -- the generator's own suite does that -- but the two things the
declaration buys a caller here:

1. the walk stops at the window the caller asked for and does not wander into history;
2. a page that came back full raises, because the service silently caps a wide window and
   a walk that stepped past it would lose every observation the cap withheld.

Both windows are real recordings of the same six hours at KSEA: one under the cap, one
asked for with `limit=10` so the page comes back full.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest
from truewire_core.exceptions import LogicError

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


WINDOW = recorded('ksea_window')
CAPPED = recorded('ksea_capped')
START = datetime.fromisoformat(WINDOW['start'].replace('Z', '+00:00'))
END = datetime.fromisoformat(WINDOW['end'].replace('Z', '+00:00'))
CAP = CAPPED['limit']

ROWS = len(json.loads((EXAMPLES / 'ksea_window.response.json').read_text())['payload']['features'])
"""How many observations the window actually holds. Moves with every re-recording; what
does not move is that it is under the service's cap, which is why that walk is one page."""


class TestTheWalk:
  @pytest.mark.asyncio
  async def test_the_window_the_caller_asked_for_is_one_page(self, client):
    """Seventy-four observations, under the service's cap, so the walk is done in one."""
    pages = [
      page
      async for page in client.stations.get_observations_paged(
        'KSEA', start=START, end=END, limit=500
      )
    ]
    assert len(pages) == 1
    assert len(pages[0]['features']) == ROWS
    assert ROWS < 500, 'this window is meant to sit under the cap, so the walk is one page'

  @pytest.mark.asyncio
  async def test_the_walk_does_not_step_past_the_callers_own_start(self, client):
    """A window walk moves backwards by its own width. Nothing before `start` was asked
    for, so nothing before `start` is requested -- the mock holds one exchange, and a
    second request would 422 rather than quietly return nothing."""
    seen = 0
    async for _ in client.stations.get_observations_paged('KSEA', start=START, end=END, limit=500):
      seen += 1
    assert seen == 1

  @pytest.mark.asyncio
  async def test_both_bounds_are_required(self, client):
    """The window is the walk. Without both ends there is nothing to move."""
    with pytest.raises(ValueError, match='pass both `start` and `end`'):
      async for _ in client.stations.get_observations_paged('KSEA', start=START):
        pass


class TestTheTruncationGuard:
  """The defect the guard exists for, on a real response.

  The service answers a window wider than its cap with the newest `limit` rows and says
  nothing about the ones it withheld. A walk that advanced past that window would skip
  them silently, and the caller would get a gap in a time series with no error anywhere.
  """

  @pytest.mark.asyncio
  async def test_a_full_page_raises_instead_of_losing_the_rest(self, client):
    """Ten rows asked for, ten rows returned: the window held more."""
    with pytest.raises(LogicError, match=f'full page of {CAP} rows'):
      async for _ in client.stations.get_observations_paged(
        'KSEA', start=START, end=END, limit=CAP
      ):
        pass

  @pytest.mark.asyncio
  async def test_the_caller_still_gets_the_page_before_the_raise(self, client):
    """The rows that did arrive are not thrown away with the error."""
    pages = []
    with pytest.raises(LogicError):
      async for page in client.stations.get_observations_paged(
        'KSEA', start=START, end=END, limit=10
      ):
        pages.append(page)
    assert len(pages) == 1
    assert len(pages[0]['features']) == CAP

  @pytest.mark.asyncio
  async def test_the_error_names_the_window_to_narrow(self, client):
    """A caller cannot act on 'something was truncated'; they can act on which window."""
    with pytest.raises(LogicError) as caught:
      async for _ in client.stations.get_observations_paged(
        'KSEA', start=START, end=END, limit=CAP
      ):
        pass
    assert str(START) in str(caught.value)
    assert 'allow_truncation=True' in str(caught.value)

  @pytest.mark.asyncio
  async def test_allow_truncation_accepts_the_loss(self, client):
    """The opt-out exists because sampling a series is a real use, and the walk then stops
    at the caller's own bound rather than raising."""
    pages = [
      page
      async for page in client.stations.get_observations_paged(
        'KSEA', start=START, end=END, limit=CAP, allow_truncation=True
      )
    ]
    assert len(pages) == 1
