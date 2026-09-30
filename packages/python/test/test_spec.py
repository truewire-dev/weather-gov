"""Invariants over the spec itself, checked rather than trusted.

`truewire check` already lints the spec against the authoring rules. What it cannot know
is the one convention this project invented: the core learns which responses to unwrap
from `meta.payload`, and the spec states the same thing in `envelope.payload` so
`truewire check` validates recordings against the whole wire frame. Two declarations of
one fact can drift, so they are compared here.

The same goes for the query form: the core joins every list filter with commas, and each
endpoint that takes one says so in `match.query_arrays`, which is what `truewire mock`
matches recordings by.
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
  """No endpoint here needs a credential, so none of them has an excuse. This is the gate
  the `Recordings` CI job runs: an endpoint added without a recorded example fails."""
  examples = path.parent / 'examples'
  requests = sorted(examples.glob('*.request.json'))
  assert requests, f'{endpoint_id(path)} has no recorded example'
  for request in requests:
    response = request.with_name(request.name.replace('.request.', '.response.'))
    assert response.exists(), f'{request.name} was recorded without its response half'


def list_filters(doc: dict) -> list[str]:
  properties = (doc['spec'].get('request') or {}).get('properties') or {}
  return sorted(name for name, schema in properties.items() if schema.get('type') == 'array')


@pytest.mark.parametrize('path', ENDPOINTS, ids=endpoint_id)
def test_a_list_filter_is_declared_comma_separated(path: Path):
  """The service reads `?id=KSEA,KPDX` and keeps only the last of `?id=KSEA&id=KPDX`, and
  the core sends the first. An endpoint with a list filter that did not declare it would
  have the mock expect repeated keys, so a two-value recording could never replay there."""
  doc = json.loads(path.read_text())
  declared = (doc.get('match') or {}).get('query_arrays', 'repeat')
  assert declared == ('comma' if list_filters(doc) else 'repeat'), endpoint_id(path)


def test_some_endpoints_take_list_filters():
  """A guard on the guard, as above."""
  with_lists = [path for path in ENDPOINTS if list_filters(json.loads(path.read_text()))]
  assert len(with_lists) == 4
