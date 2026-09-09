"""Shared fixtures: a real `Weather` client pointed at the local mock server.

`base_url` puts `api.weather.gov` on the mock's HTTP server, exactly the way a caller
would point it at a proxy. Nothing here reaches the network.
"""

from pathlib import Path

import pytest
from truewire.mock import running_mock_servers

from weather_gov import Weather

PROJECT = Path(__file__).resolve().parents[3]

CONTACT = 'tests@truewire.dev'
"""What the tests identify themselves as. The mock does not read it; the client requires
it, which is the point -- a caller cannot forget to say who they are."""


@pytest.fixture
def mock_servers():
  with running_mock_servers(PROJECT) as servers:
    yield servers


@pytest.fixture
def client(mock_servers):
  """The generated client, built exactly as a user would, against the mock's address."""
  return Weather.new(contact=CONTACT, base_url=mock_servers.http_base_url, validate=True)
