"""`Weather.new(proxy=...)`: every call goes through the proxy the caller names.

The proxy here is a real one on a local port: it reads the absolute-form request line an
HTTP proxy is sent, forwards the request to the mock, and records what it forwarded.
"""

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from weather_gov import Weather

CONTACT = 'tests@truewire.dev'


@pytest_asyncio.fixture
async def proxy() -> AsyncIterator[tuple[str, list[str]]]:
  seen: list[str] = []

  async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    head = (await reader.readuntil(b'\r\n\r\n')).decode()
    method, url, _ = head.split('\r\n', 1)[0].split(' ')
    seen.append(f'{method} {url}')
    async with httpx.AsyncClient(trust_env=False) as upstream:
      answer = await upstream.request(method, url)
    writer.write(
      b'HTTP/1.1 %d OK\r\ncontent-type: %s\r\ncontent-length: %d\r\nconnection: close\r\n\r\n'
      % (answer.status_code, answer.headers['content-type'].encode(), len(answer.content))
      + answer.content
    )
    await writer.drain()
    writer.close()

  server = await asyncio.start_server(handle, '127.0.0.1', 0)
  port = server.sockets[0].getsockname()[1]
  async with server:
    yield f'http://127.0.0.1:{port}', seen


@pytest.mark.asyncio
async def test_a_call_goes_through_the_named_proxy(mock_servers, proxy, monkeypatch):
  """Named on the constructor, not in the environment, and the environment is ignored."""
  url, seen = proxy
  monkeypatch.setenv('HTTP_PROXY', 'http://127.0.0.1:9')
  async with Weather.new(contact=CONTACT, base_url=mock_servers.http_base_url, proxy=url) as client:
    point = await client.points.get_point(latitude=47.6062, longitude=-122.3321)
  assert point['gridId'] == 'SEW'
  assert seen == [f'GET {mock_servers.http_base_url}/points/47.6062,-122.3321']
