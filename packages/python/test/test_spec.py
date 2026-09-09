"""Invariants over the spec itself, checked rather than trusted.

`truewire check` already lints the spec against the authoring rules. What it cannot know
is the one convention this project invented: the core learns which responses to unwrap
from `meta.payload`, and the spec states the same thing in `envelope.payload` so
`truewire check` validates recordings against the whole wire frame. Two declarations of
one fact can drift, so they are compared here.
"""

import json
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[3]

ENDPOINTS = sorted((PROJECT / 'spec/endpoints').glob('*/*/endpoint.json'))


def endpoint_id(path: Path) -> str:
  return f'{path.parent.parent.name}.{path.parent.name}'


@pytest.mark.parametrize('path', ENDPOINTS, ids=endpoint_id)
def test_the_envelope_and_the_meta_agree(path: Path):
  """`meta.payload` is what the core unwraps; `envelope.payload` is what the spec says it
  unwraps. An endpoint that declares one without the other is silently broken: the caller
  gets the wrapper, or validation runs against the wrong half."""
  doc = json.loads(path.read_text())
  declared = (doc.get('envelope') or {}).get('payload')
  told = (doc.get('meta') or {}).get('payload')
  assert declared == told, (
    f'{endpoint_id(path)} declares envelope.payload={declared!r} but tells the core '
    f'meta.payload={told!r}'
  )


def test_some_endpoints_unwrap_and_some_do_not():
  """A guard on the guard: if every endpoint stopped declaring an envelope, the test above
  would pass vacuously and the unwrapping would be untested."""
  payloads = [
    (json.loads(path.read_text()).get('envelope') or {}).get('payload') for path in ENDPOINTS
  ]
  assert payloads.count('properties') == 5
  assert payloads.count(None) == len(ENDPOINTS) - 5


@pytest.mark.parametrize('path', ENDPOINTS, ids=endpoint_id)
def test_every_endpoint_has_a_recording(path: Path):
  """No endpoint here needs a credential, so none of them has an excuse. This is the gate
  the `Recordings` CI job runs: an endpoint added without a recorded example fails."""
  examples = path.parent / 'examples'
  requests = sorted(examples.glob('*.request.json'))
  assert requests, f'{endpoint_id(path)} has no recorded example'
  for request in requests:
    response = request.with_name(request.name.replace('.request.', '.response.'))
    assert response.exists(), f'{request.name} was recorded without its response half'
