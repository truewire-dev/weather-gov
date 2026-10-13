// TRU-1315: every listed product type through products.listLocationsForType with validation on,
// plus listLocations, a two-type listProducts, and the validate:false path.
// Run from the repo root after `cd packages/typescript && yarn build`.
import { writeFileSync } from 'node:fs'
import { Weather } from '../../packages/typescript/dist/core/index.js'

const client = Weather.new({ contact: 'hello@truewire.dev' })
async function retry(f) {
  for (let i = 0; ; i++) {
    try { return await f() } catch (e) {
      if (i < 4 && e?.status >= 500) { await new Promise(r => setTimeout(r, 1000 * (i + 1))); continue }
      throw e
    }
  }
}
const types = (await retry(() => client.products.listProductTypes()))['@graph'].map(t => t.productCode)
let empty = 0, full = 0
const failures = []
for (const code of types) {
  try {
    const { locations } = await retry(() => client.products.listLocationsForType({ type_id: code }))
    if (Array.isArray(locations) || typeof locations !== 'object') throw new Error('not a map')
    Object.keys(locations).length === 0 ? empty++ : full++
  } catch (e) { failures.push({ code, error: String(e), status: e?.status }) }
}
console.log(`${types.length} types: ${full} maps, ${empty} empty maps, ${failures.length} failures`)
const raw = await retry(() => client.products.listLocationsForType({ type_id: 'AGF' }, { validate: false }))
console.log('validate:false AGF locations =', JSON.stringify(raw.locations))
const all = await retry(() => client.products.listLocations())
console.log('listLocations', Object.keys(all.locations).length)
const two = await retry(() => client.products.listProducts({ type: ['AFD', 'ZFP'], location: ['SEW'], limit: 50 }))
console.log('listProducts AFD,ZFP codes', [...new Set(two['@graph'].map(p => p.productCode))].sort().join(','))
writeFileSync(process.env.OUT ?? '/dev/null', JSON.stringify(failures, null, 1))
process.exit(failures.length === 0 ? 0 : 1)
