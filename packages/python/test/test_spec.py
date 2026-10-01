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
  assert payloads.count('properties') == 6
  assert payloads.count(None) == len(ENDPOINTS) - 6


@pytest.mark.parametrize('path', ENDPOINTS, ids=endpoint_id)
def test_every_endpoint_has_a_recording(path: Path):
  """No endpoint here needs a credential, so the only excuse is the service itself failing,
  declared as `unverified` (ADR 0001). This is the gate the `Recordings` CI job runs: an
  endpoint added without a recorded example, or a declaration, fails."""
  examples = path.parent / 'examples'
  requests = sorted(examples.glob('*.request.json'))
  if json.loads(path.read_text()).get('unverified'):
    assert not requests, f'{endpoint_id(path)} is declared unverified but has examples'
    return
  assert requests, f'{endpoint_id(path)} has no recorded example'
  for request in requests:
    response = request.with_name(request.name.replace('.request.', '.response.'))
    assert response.exists(), f'{request.name} was recorded without its response half'


def test_seven_radar_operations_are_recorded_and_the_profiler_is_not():
  """The radar group is eight operations: seven recorded, and `get_profiler`, which every
  profiler answered with a 404 on 2026-10-01. A 404 body is never saved as an example."""
  radar = {endpoint_id(path): path for path in ENDPOINTS if path.parent.parent.name == 'radar'}
  unverified = {
    name: json.loads(path.read_text())['unverified']
    for name, path in radar.items()
    if 'unverified' in json.loads(path.read_text())
  }
  assert len(radar) == 8
  assert set(unverified) == {'radar.get_profiler'}
  assert unverified['radar.get_profiler']['reason'] == 'runtime_error'
  assert '2026-10-01' in unverified['radar.get_profiler']['detail']
  assert not (radar['radar.get_profiler'].parent / 'examples').exists()
  assert len(radar) - len(unverified) == 7


def test_the_profiler_is_in_the_inventory_and_the_spec():
  """Documented and answering JSON, so built and unverified rather than excluded."""
  inventory = json.loads((PROJECT / 'spec/inventory.json').read_text())
  (entry,) = [e for e in inventory['endpoints'] if e['path'] == '/radar/profilers/{stationId}']
  assert entry == {
    'method': 'GET',
    'path': '/radar/profilers/{stationId}',
    'endpoint': 'radar.get_profiler',
  }
  assert inventory['approved'] is None
  spec = json.loads((PROJECT / 'spec/endpoints/radar/get_profiler/endpoint.json').read_text())[
    'spec'
  ]
  assert spec['path'] == '/radar/profilers/{station_id}'
  assert set(spec['request']['properties']) == {'station_id', 'time', 'interval'}
  assert spec['request']['required'] == ['station_id']
  # No field is invented for a body nobody has seen.
  assert not {'type', 'properties', '$ref'} & set(spec['response'])


def test_the_queue_request_keeps_created():
  """`created` answered 503 upstream, which is no reason to drop a documented filter."""
  spec = json.loads((PROJECT / 'spec/endpoints/radar/get_queue/endpoint.json').read_text())
  assert spec['spec']['request']['properties']['created']['type'] == 'string'
  assert 'created' not in spec['spec']['request']['required']
