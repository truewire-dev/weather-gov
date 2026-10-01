import { Weather } from '../src/weather-gov/core/index.js'
import { ListSigmets } from '../src/weather-gov/aviation/list_sigmets.js'

declare const client: Weather
declare const endpoint: ListSigmets

async function router() {
  const raw = await client.aviation.listSigmets(undefined, { validate: false })
  // @ts-expect-error Raw JSON must not advertise decoded Date methods.
  raw.features[0].properties.issueTime.toISOString()
  const explicit = await client.aviation.listSigmets({}, { validate: false })
  // @ts-expect-error The explicit-empty control correctly returns unknown.
  explicit.features[0].properties.issueTime.toISOString()
  const validated = await client.aviation.listSigmets()
  validated.features[0].properties.issueTime.toISOString()
}
async function leaf() {
  const raw = await endpoint.listSigmets(undefined, { validate: false })
  // @ts-expect-error Raw JSON must not advertise decoded Date methods.
  raw.features[0].properties.issueTime.toISOString()
}
void router
void leaf
