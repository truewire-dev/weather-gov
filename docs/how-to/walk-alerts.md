# Walk alerts with a cursor

`alerts.list_alerts` returns one page. Its `pagination.next` is a URL, so the
client has no generated pagination method for this endpoint. Extract the `cursor`
query value with a standard URL parser, which percent-decodes it exactly once.
Do not send the whole URL or an encoded substring as the cursor.

Keep the original filters and `limit` on every request: the next URL can omit them.
Stop when the page is empty or the next cursor is absent. A short non-empty page
is not a stopping condition: live review observed 100 rows, then 76 with a next
link, then an empty page.

```python
from collections.abc import AsyncIterator
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from weather_gov import Weather
from weather_gov.schemas import AlertFeature


async def walk_alerts(
  client: Weather, *, start: datetime, end: datetime, limit: int = 100
) -> AsyncIterator[AlertFeature]:
  cursor: str | None = None
  while True:
    page = await client.alerts.list_alerts(
      start=start, end=end, status=['actual'], limit=limit, cursor=cursor
    )
    if not page['features']:
      return
    for feature in page['features']:
      yield feature
    next_url = page.get('pagination', {}).get('next', '')
    cursor = parse_qs(urlsplit(next_url).query).get('cursor', [None])[0]
    if not cursor:
      return
```

In TypeScript, use `new URL(nextUrl).searchParams.get('cursor')`. In Rust, use
`url::Url::parse(next_url)?.query_pairs()` (add the `url` crate) and take the
`cursor` value. Both decode the query value; neither restores filters omitted
from the URL, so retain those from your original request.
