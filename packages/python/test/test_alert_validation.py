"""Offline mutations of a recorded alert, never claimed as live recordings."""

import json
from pathlib import Path

import pytest
from truewire_core.exceptions import ValidationError
from truewire_core.validation import validator

from weather_gov.schemas import Alert

RECORDING = (
  Path(__file__).resolve().parents[3]
  / 'spec/endpoints/alerts/list_alerts/examples/first_page.response.json'
)


def alert():
  return json.loads(RECORDING.read_text())['payload']['features'][0]['properties']


@pytest.mark.parametrize('field', ['description', 'response'])
def test_explicit_null_is_preserved(field):
  body = alert()
  body[field] = None
  assert validator(Alert).python(body)[field] is None


def test_non_null_values_and_optional_response():
  body = alert()
  body.update(description='Take shelter.', response='Shelter')
  parsed = validator(Alert).python(body)
  assert parsed['description'] == 'Take shelter.'
  assert parsed.get('response') == 'Shelter'
  del body['response']
  assert 'response' not in validator(Alert).python(body)


def test_description_is_still_required():
  body = alert()
  del body['description']
  with pytest.raises(ValidationError):
    validator(Alert).python(body)


@pytest.mark.parametrize(
  ('field', 'value'),
  [('description', 42), ('description', {}), ('response', 'shelter'), ('response', 42)],
)
def test_invalid_non_null_values_still_fail(field, value):
  body = alert()
  body[field] = value
  with pytest.raises(ValidationError):
    validator(Alert).python(body)
