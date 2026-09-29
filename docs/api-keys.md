# API keys

The National Weather Service API has no keys, no accounts and no quota to buy. It asks one
thing of a caller: say who you are in the `User-Agent` header, with contact details, so
the service can reach you if your traffic misbehaves. A request without one is refused
with 403 before it reaches the API.

That contact is the one required argument of every client. It has no default, because a
default would be a lie about who is calling. The client sends it on every call as
`User-Agent: truewire-weather-gov (<contact>)`.

## What to put in it

An email address you read, or the URL of your project's page or repository. It is not a
secret. Use the same one from every machine that runs your code, so that the service sees
one caller.

## Setting it

Python: `contact=` on `Weather.new`.

```python
from weather_gov import Weather


async def main() -> None:
  async with Weather.new(contact='you@example.com') as client:
    office = await client.offices.get_office('SEW')
    print(office['name'])
```

TypeScript: the `contact` option of `Weather.new`.

```ts
import { Weather } from '@truewire/weather-gov'

const client = Weather.new({ contact: 'you@example.com' })
const office = await client.offices.getOffice({ office_id: 'SEW' })
console.log(office.name)
```

Rust: the argument of `Weather::new`, or `CoreOptions::new` when you also set other
options. It is a `String`, not an `Option<String>`.

```rust
use weather_gov::core::CoreOptions;
use weather_gov::Weather;

fn clients() -> (Weather, Weather) {
    let simple = Weather::new("you@example.com");
    let configured = Weather::with_options(
        CoreOptions::new("you@example.com").base_url("http://127.0.0.1:8080"),
    );
    (simple, configured)
}
```

`base_url` points the client at another host, such as a `truewire mock` serving the
recordings. The contact is sent there too.

## What to refuse

- **A key.** Nothing here reads one, so a page or a package that asks for a weather.gov API
  key is not talking about this API.
- **An empty or placeholder contact.** `you@example.com` is for these pages. Any string is
  accepted, but the service asks for a way to reach you, and one that reaches nobody can get
  your traffic blocked.
