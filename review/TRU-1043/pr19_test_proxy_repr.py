"""TRU-1043 review of weather-gov #19: a proxy password must not reach repr(client).

Run from the repo root: .venv/bin/python -m pytest review/test_proxy_repr.py -q
"""

from weather_gov import Weather


def test_repr_hides_proxy_credentials():
  client = Weather.new(contact='tests@truewire.dev', proxy='http://user:S3CRET@127.0.0.1:3128')
  assert 'S3CRET' not in repr(client)
