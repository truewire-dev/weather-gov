/**
 * Review harness for TRU-31: drive the generated `getObservationsPaged` against a fake
 * service that answers like weather.gov over the recorded 76 KSEA rows (newest first,
 * `start`/`end` inclusive, at most `min(limit, 500)` rows kept from the newest end).
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import type { HttpEndpoint } from '@truewire/core'
import { GetObservations, type ObservationCollection } from '../src/weather-gov/stations/get_observations.js'
import type { DefaultMeta } from '../src/weather-gov/meta.js'
import { projectRoot } from '../test/setup.js'

const recorded = JSON.parse(readFileSync(path.join(projectRoot,
  'spec/endpoints/stations/get_observations/examples/ksea_window.response.json'), 'utf8')).payload as ObservationCollection
const ROWS = recorded.features as unknown as { properties: { timestamp: string } }[]

function fake(log: Record<string, unknown>[]): HttpEndpoint<DefaultMeta> {
  return {
    async request(call: any) {
      const q = call.requestCodec.dump(call.request) as Record<string, any>
      log.push(q)
      if (q.limit !== undefined && (q.limit < 1 || q.limit > 500)) throw new Error(`400: limit ${q.limit}`)
      const lo = q.start ? Date.parse(q.start) : -Infinity
      const hi = q.end ? Date.parse(q.end) : Infinity
      const kept = ROWS.filter(r => { const t = Date.parse(r.properties.timestamp); return t >= lo && t <= hi })
      const body = { type: 'FeatureCollection', features: kept.slice(0, Math.min(q.limit ?? 500, 500)) }
      return (call.validate === false ? body : call.responseCodec.parse(body)) as any
    },
  }
}

const SPAN = { station_id: 'KSEA', start: new Date('2026-09-09T02:00:00Z'), end: new Date('2026-09-09T08:00:00Z') }

describe('getObservationsPaged', () => {
  it('limit 10 walks all 76 rows once, newest first', async () => {
    const log: Record<string, unknown>[] = []
    const rows = await new GetObservations(fake(log)).getObservationsPaged({ ...SPAN, limit: 10 })
    expect(rows.length).toBe(76)
    expect(new Set(rows.map(r => r.id)).size).toBe(76)
    console.log('limit 10 requests:', log.length, 'second end sent as', log[1]?.end)
  })

  it('limit 1 (in the declared range [1, 500]) walks all 76 rows', async () => {
    const rows = await new GetObservations(fake([])).getObservationsPaged({ ...SPAN, limit: 1 })
    expect(rows.length).toBe(76)
  })

  it('validate: false walks the same rows', async () => {
    const rows = await new GetObservations(fake([])).getObservationsPaged({ ...SPAN, limit: 10 }, { validate: false })
    expect(rows.length).toBe(76)
  })

  it('a page can be checkpointed and resumed', async () => {
    const paging = new GetObservations(fake([])).getObservationsPaged({ ...SPAN, limit: 30 })
    const first = await paging.pages().next()
    const rest = await paging.resume(first.value!.next!)
    expect(first.value!.rows.length + rest.length).toBe(76)
  })
})

describe('limit outside [1, 500]', () => {
  for (const limit of [600, 0, 2.5]) {
    it(`limit ${limit}`, async () => {
      const log: Record<string, unknown>[] = []
      let outcome: string
      try { outcome = `ok ${(await new GetObservations(fake(log)).getObservationsPaged({ ...SPAN, limit })).length} rows` }
      catch (e) { outcome = `${(e as Error).constructor.name}: ${(e as Error).message}` }
      console.log(`limit ${limit}: sent`, log.map(q => q.limit), '->', outcome)
    })
  }
})

describe('checkpoint through JSON', () => {
  it('resume from a JSON-saved page.next', async () => {
    const log: Record<string, unknown>[] = []
    const paging = new GetObservations(fake(log)).getObservationsPaged({ ...SPAN, limit: 30 })
    const first = (await paging.pages().next()).value!
    const saved = JSON.parse(JSON.stringify(first.next))
    let outcome: string
    try { outcome = `ok ${(await paging.resume(saved)).length} rows (expected ${76 - first.rows.length})` }
    catch (e) { outcome = `${(e as Error).constructor.name}: ${(e as Error).message}` }
    console.log('json resume ->', outcome, '| saved state bytes', JSON.stringify(first.next).length)
  })
})
