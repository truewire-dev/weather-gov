import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { Transport } from '../../packages/typescript/src/weather-gov/core/http.js'
import { Offices } from '../../packages/typescript/src/weather-gov/offices/index.js'
import { GetBriefing } from '../../packages/typescript/src/weather-gov/offices/get_briefing.js'
import {
  AlertFeature, AlertGeometry, PointGeometry, Position, ZoneFeature, ZoneGeometry, ZoneKind,
} from '../../packages/typescript/src/weather-gov/types/index.js'

// Exercise the shared public aliases without casts or a substituted runtime.
const position: Position = [-122.3, 47.45]
const point: PointGeometry = { type: 'Point', coordinates: position }
assert.deepEqual(PointGeometry.parse(PointGeometry.dump(point)), point)
const outline: ZoneGeometry = null
const alertOutline: AlertGeometry = { type: 'Polygon', coordinates: [[position, position]] }
assert.equal(ZoneGeometry.parse(outline), null)
assert.deepEqual(AlertGeometry.parse(AlertGeometry.dump(alertOutline)), alertOutline)
const kind: ZoneKind = 'county'
assert.equal(ZoneKind.parse(kind), kind)

function recorded(file: string): unknown {
  return JSON.parse(readFileSync(`spec/endpoints/${file}`, 'utf8')).payload
}
const zone = ZoneFeature.parse(recorded('zones/get_zone/examples/seattle.response.json'))
const shared: ZoneGeometry = zone.geometry
assert.equal(shared?.type, 'Polygon')
const alert = AlertFeature.parse(recorded('alerts/get_alert/examples/one.response.json'))
const optional: AlertGeometry | undefined = alert.geometry
assert.ok(optional === undefined || optional === null || typeof optional === 'object')
console.log('PASS: public shared aliases and recorded geometry codecs')

// Serve the exact recorded response through the real transport, without live HTTP.
const body = recorded('offices/get_briefing/examples/active.response.json')
globalThis.fetch = async () => new Response(JSON.stringify(body), { status: 200 })
const transport = new Transport({ contact: 'tests@truewire.dev' })
const endpoint = new GetBriefing(transport)
const router = new Offices(transport)
const request = { office_id: 'AKQ' }
const checked = await router.getBriefing(request)
assert.equal(typeof checked.briefing!.startTime.getTime(), 'number')
const raw = await router.getBriefing(request, { validate: false })
if (false) {
  // @ts-expect-error The literal-false overload correctly returns unknown.
  raw.briefing.startTime.getTime()
}

// Parameters selects the final public overload's exported CallOptions type.
const options: NonNullable<Parameters<Offices['getBriefing']>[1]> = { validate: false }
let defects = 0
for (const [name, result] of [
  ['endpoint', await endpoint.getBriefing(request, options)],
  ['router', await router.getBriefing(request, options)],
] as const) {
  try {
    // This compiles as TimestampIso/Date, but the recorded wire value is a string.
    result.briefing!.startTime.getTime()
  } catch (error) {
    assert.ok(error instanceof TypeError)
    console.error(`${name}: ${error.message}`)
    defects++
  }
}
assert.equal(defects, 2, 'Both widened-options calls reproduce the same unsound return type')
process.exitCode = 1
