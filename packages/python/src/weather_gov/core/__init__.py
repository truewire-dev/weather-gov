"""Hand-written core for the weather.gov client: the transport, the envelope, the error
mapping, and the base classes every generated endpoint subclasses.

Nothing here is generated, and regenerating the client never touches it. Every generated
endpoint subclasses `Endpoint` and calls `self.request(...)`.

Three things about this API shape the core:

1. **No credentials, but you must say who you are.** The National Weather Service asks
   every caller to identify itself in `User-Agent`, with contact details, so it can reach
   you if your traffic misbehaves. `Weather.new(contact=...)` is how; there is no key and
   nothing to keep secret.
2. **Most responses are GeoJSON.** A forecast arrives as a `Feature` whose `geometry` is
   the outline of the grid cell the caller already named. Those endpoints declare
   `envelope.payload` in the spec, repeated as `meta.payload` here, and `request()`
   unwraps them before validating -- so a caller gets the forecast, not the wrapper.
   Endpoints whose geometry is real data (an alert's polygon) declare no envelope and are
   returned whole.
3. **A repeated filter is a repeated query key.** `state`, `area`, `severity` and the rest
   take lists, and travel as `?state=WA&state=OR`.
"""

import json
from dataclasses import dataclass, field
from types import UnionType
from urllib.parse import quote

from typing_extensions import Any, Self, TypeVar, cast

from truewire_core.exceptions import ApiError, BadRequest, RateLimited
from truewire_core.http import HttpClient
from truewire_core.validation import validator

from ..meta import DefaultMeta as Meta

T = TypeVar('T')

API = 'https://api.weather.gov'
"""The one host. There is no staging environment and no versioned prefix: the API is
versioned through the `Accept` header instead."""

GEO_JSON = 'application/geo+json'
"""What most of this API answers in. The service also serves `application/ld+json` and
`application/vnd.noaa.dwml+xml` from the same paths, so asking matters -- and asking for
`application/geo+json` is what pins the response shapes these schemas describe.

The offices and product-type endpoints answer in JSON-LD regardless of what is asked for;
their schemas describe what they actually send."""


def user_agent(contact: str) -> str:
  """The `User-Agent` the service asks for: who is calling, and how to reach them.

  The published guidance is a string identifying the application with contact
  information, and a caller that sends nothing useful can be blocked. So `contact` is a
  required argument rather than an optional one with a default that would be a lie.
  """
  return f'truewire-weather-gov ({contact})'


def raise_for_status(method: str, path: str, status: int, text: str) -> None:
  """Map a non-2xx answer onto the runtime's exceptions.

  The service answers errors in RFC 7807 problem detail (`{title, detail, status,
  correlationId, ...}`), and a bad parameter adds a `parameterErrors` list naming exactly
  which one and why. That list is the most useful thing in the body, so it is what the
  message leads with when it is there.
  """
  reason = text[:300]
  try:
    body = json.loads(text)
  except ValueError:
    body = None
  if isinstance(body, dict):
    problems = body.get('parameterErrors')
    if isinstance(problems, list) and problems:
      reason = '; '.join(
        f'{item.get("parameter")}: {item.get("message")}'
        for item in problems
        if isinstance(item, dict)
      )
    elif isinstance(body.get('detail'), str):
      reason = body['detail']
    elif isinstance(body.get('title'), str):
      reason = body['title']
  message = f'{method} {path}: HTTP {status}: {reason}'
  if status == 400:
    raise BadRequest(message)
  if status == 429:
    raise RateLimited(message)
  raise ApiError(message)


def render(request: Any, request_type: type[Any] | UnionType | None) -> dict[str, Any]:
  """The request's fields in wire form, without the ones left unset.

  Rendering through the request's own type applies every declared wire format, so a
  `start` passed as a `datetime` becomes the ISO 8601 string the service parses rather
  than `str()` of a `datetime`.
  """
  if request is None:
    return {}
  if request_type is None:
    rendered = dict(request)
  else:
    rendered = json.loads(validator(cast(type, request_type)).dump(request))
  return {k: v for k, v in rendered.items() if v is not None}


def unwrap(raw: Any, payload: str | None) -> Any:
  """Read the declared envelope payload off a decoded response body.

  `payload` is the dotted path an endpoint declared, `None` for an endpoint that declares
  no envelope. An endpoint that declares one and does not get it is a wire change, not a
  missing optional field, so it raises rather than returning `None` for validation to
  report as a type error three frames later.
  """
  if payload is None:
    return raw
  value = raw
  for key in payload.split('.'):
    if not isinstance(value, dict) or key not in value:
      raise ApiError(f'response has no `{payload}` to unwrap; the wire shape has changed')
    value = value[key]
  return value


@dataclass(kw_only=True)
class Transport:
  """The HTTP transport: one host, one connection pool, one `User-Agent`."""

  base_url: str
  contact: str
  http: HttpClient = field(default_factory=HttpClient)
  validate: bool = True

  def headers(self) -> dict[str, str]:
    """Headers for one call. The same on every call: there is nothing per-endpoint."""
    return {'Accept': GEO_JSON, 'User-Agent': user_agent(self.contact)}

  async def send(self, method: str, path: str, *, params: dict[str, Any]) -> bytes:
    """Send one request and return the body; a non-2xx status raises.

    A `{name}` placeholder in the path is filled from the request and removed from the
    query. The value is percent-encoded because some of them need it: an alert id is
    `urn:oid:2.49.0.1.840.0.<hash>.001.1`, and a station or office code never does -- so
    encoding always is simpler than deciding per parameter. `/` is encoded too: no path
    parameter here is a path fragment, so a `/` in one would be an injected path segment.
    """
    filled = path
    for name, value in list(params.items()):
      if f'{{{name}}}' in filled:
        filled = filled.replace(f'{{{name}}}', quote(str(value), safe=''))
        params.pop(name)
    response = await self.http.request(
      method,
      self.base_url.rstrip('/') + '/' + filled.lstrip('/'),
      params=params or None,
      headers=self.headers(),
    )
    if response.status_code >= 400:
      raise_for_status(method, filled, response.status_code, response.text)
    return response.content


@dataclass(kw_only=True)
class ClientBase:
  """Root client: the one HTTP transport every endpoint group shares."""

  client: Transport

  @classmethod
  def new(cls, *, contact: str, base_url: str = API, validate: bool = True) -> Self:
    """Create a client.

    Args:
      contact: How the service can reach you -- an email address or a project URL. It is
        sent in `User-Agent` on every call, which the service asks of every caller. There
        is no API key: this is the whole of identifying yourself.
      base_url: The host to call. The live API by default; a `truewire mock` address in
        tests.
      validate: Whether responses are validated against their declared types by default.
        A call's own `validate=` overrides it.
    """
    return cls(client=Transport(base_url=base_url, contact=contact, validate=validate))

  async def __aenter__(self) -> Self:
    return self

  async def __aexit__(self, exc_type, exc_value, traceback):
    await self.client.http.__aexit__(exc_type, exc_value, traceback)


@dataclass(kw_only=True, frozen=True)
class Endpoint:
  """Base for every generated endpoint class: the shared HTTP transport."""

  client: Transport

  async def request(
    self,
    request: Any = None,
    *,
    method: str,
    path: str,
    validate: bool | None = None,
    request_type: type[Any] | UnionType | None = None,
    response_type: type[T] | UnionType | None = None,
    meta: Meta = {},
  ) -> T:
    """Send one request, unwrap the declared envelope, and validate what is left.

    Everything here is a `GET` with query parameters, so there is no body to build. The
    order matters: the envelope is read off the decoded body first, and `response_type`
    describes the unwrapped value, not the wire frame the spec's response schema
    describes (ADR 0010).
    """
    params = render(request, request_type)
    raw = await self.client.send(method, path, params=params)
    if response_type is None:
      return None  # type: ignore[return-value]
    value = unwrap(json.loads(raw), meta.get('payload'))
    check = self.client.validate if validate is None else validate
    if check:
      return validator(cast(type, response_type)).python(value)
    return value
