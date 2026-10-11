import { Weather } from '../../packages/typescript/dist/core/index.js'
const c = Weather.new({ contact: 'hello@truewire.dev' })
const t0 = Date.now()
const all = await c.products.listProducts({ limit: 500 })
console.log('listProducts 500 validated', all['@graph'].length, all['@graph'][0].issuanceTime instanceof Date)
const two = await c.products.listProducts({ type: ['AFD', 'TOR', 'ZFP'], start: new Date(Date.now() - 6 * 3600e3), limit: 500 })
console.log('three types', [...new Set(two['@graph'].map(p => p.productCode))].sort())
const id = two['@graph'][0].id
const p = await c.products.getProduct({ product_id: id })
console.log('getProduct', p.productCode, typeof p.productText, p.productText?.length)
const latest = await c.products.getLatestProduct({ type_id: 'AFD', location_id: 'SEW' })
console.log('latest', latest.issuingOffice, latest.issuanceTime.toISOString())
const locs = await c.products.listLocations()
const nulls = Object.values(locs.locations).filter(v => v === null).length
console.log('locations', Object.keys(locs.locations).length, 'null names', nulls)
const lt = await c.products.listLocationsForType({ type_id: 'AFD' })
console.log('locationsForType', Object.keys(lt.locations).length)
const tl = await c.products.listTypesForLocation({ location_id: 'SEW' })
console.log('typesForLocation', tl['@graph'].length)
const bt = await c.products.listProductsByType({ type_id: 'TOR' })
console.log('byType TOR', bt['@graph'].length)
const btl = await c.products.listProductsByTypeAndLocation({ type_id: 'AFD', location_id: 'SEW' })
console.log('byTypeAndLocation', btl['@graph'].length)
const types = await c.products.listProductTypes()
console.log('types', types['@graph'].length)
for (const code of ['ADM', 'PNS', 'RR5', 'SPS', 'MTR']) {
  try { const r = await c.products.listProductsByType({ type_id: code }); console.log(code, r['@graph'].length) } catch (e) { console.log(code, 'ERR', String(e).slice(0, 300)) }
}
