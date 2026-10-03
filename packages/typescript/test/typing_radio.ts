import type { Weather } from '../src/weather-gov/core/index.js'
import type { ListTransmitters } from '../src/weather-gov/radio/list_transmitters.js'
import type { GetTransmitter } from '../src/weather-gov/radio/get_transmitter.js'

declare const client: Weather
declare const endpoint: ListTransmitters
declare const requiredEndpoint: GetTransmitter

async function rawRouter() {
  const raw = await client.radio.listTransmitters(undefined, { validate: false })
  // @ts-expect-error Unvalidated data must be unknown, including an omitted request.
  raw['@graph'].map(row => row.callSign)
}

async function rawEndpoint() {
  const raw = await endpoint.listTransmitters(undefined, { validate: false })
  // @ts-expect-error The endpoint class must provide the same unknown return type.
  raw['@graph'].map(row => row.callSign)
}

async function controls() {
  const raw = await client.radio.listTransmitters({}, { validate: false })
  // @ts-expect-error An explicit empty request correctly returns unknown already.
  raw['@graph']
  const checked = await client.radio.listTransmitters()
  checked['@graph'].map(row => row.callSign)
}

void rawRouter
void rawEndpoint
void controls

async function requiredRequests() {
  // @ts-expect-error A required router request must not become optional.
  await client.radio.getTransmitter(undefined, { validate: false })
  // @ts-expect-error A required endpoint request must not become optional.
  await requiredEndpoint.getTransmitter(undefined, { validate: false })
}

void requiredRequests
