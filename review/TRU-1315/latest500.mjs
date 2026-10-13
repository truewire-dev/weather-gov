// getLatestProduct for a location that has issued nothing of the type: the service answers 500.
import { ApiError } from '@truewire/core'
import { Weather } from '../../packages/typescript/dist/core/index.js'
const client = Weather.new({ contact: 'hello@truewire.dev' })
try { await client.products.getLatestProduct({ type_id: 'CLI', location_id: 'OKX' }); console.log('no error') }
catch (e) { console.log(e.constructor.name, e instanceof ApiError, e.status, String(e).slice(0, 160)) }
const list = await client.products.listProductsByTypeAndLocation({ type_id: 'CLI', location_id: 'OKX' })
console.log('list rows', list['@graph'].length)
