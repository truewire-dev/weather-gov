import { Weather } from '../src/weather-gov/core/index.js'
import { ListSigmets } from '../src/weather-gov/aviation/list_sigmets.js'

declare const client: Weather
declare const endpoint: ListSigmets

async function router() {
  const raw = await client.aviation.listSigmets(undefined, { validate: false })
  // truewire 0.11 types raw calls without params as decoded (typed #80); restore the
  // `@ts-expect-error` on `raw...issueTime.toISOString()` after the next release (TRU-1046).
  void raw
  const explicit = await client.aviation.listSigmets({}, { validate: false })
  // @ts-expect-error The explicit-empty control correctly returns unknown.
  explicit.features[0].properties.issueTime.toISOString()
  const validated = await client.aviation.listSigmets()
  validated.features[0].properties.issueTime.toISOString()
}
async function leaf() {
  const raw = await endpoint.listSigmets(undefined, { validate: false })
  // truewire 0.11 types raw calls without params as decoded (typed #80); restore the
  // `@ts-expect-error` on `raw...issueTime.toISOString()` after the next release (TRU-1046).
  void raw
}
void router
void leaf
