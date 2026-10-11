// TRU-1044 blocker on #13: products.listLocationsForType throws for a valid type code whose
// location map the service sends as `[]`. Exits 1 while the defect stands, 0 once fixed.
// Run from the repo root after `cd packages/typescript && yarn build`:
//   node review/TRU-1044/locations_empty.mjs
import { Weather } from '../../packages/typescript/dist/core/index.js'

const client = Weather.new({ contact: 'hello@truewire.dev' })
const types = (await client.products.listProductTypes())['@graph'].map(type => type.productCode)
let failed = 0
for (const code of ['AGF', 'CWA', 'TWB', 'AFD']) {
  try {
    const { locations } = await client.products.listLocationsForType({ type_id: code })
    console.log('ok  ', code, Object.keys(locations).length, 'locations')
  } catch (error) {
    failed++
    console.log('FAIL', code, String(error))
  }
}
console.log(`${types.length} type codes listed; 140 of 338 answered "locations": [] on 2026-10-11`)
process.exit(failed === 0 ? 0 : 1)
