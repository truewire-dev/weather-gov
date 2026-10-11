/**
 * The declared `seek` walk, `stations.getObservationsPaged`: the TypeScript half of
 * `packages/python/test/test_pagination.py`.
 *
 * The walk moves `end` back to the oldest observation of each page that came back full
 * (ADR 0013). The algorithm is the toolchain's and `@truewire/core`'s suite covers it; what
 * is worth testing here is what the declaration buys a caller on this service's real
 * responses:
 *
 * 1. a span under the cap is one request, and the walk does not wander past it;
 * 2. a capped page is progress rather than the whole span: the next request ends at the
 *    oldest observation the capped page held, which is only right because the service keeps
 *    the newest rows when it caps (the declared `anchor: end`);
 * 3. the service's `end` is exclusive, so that next request does not return the boundary
 *    observation again, and the whole span comes back once, newest first.
 *
 * The first two run against `truewire mock`, which serves the two recordings of the same six
 * hours at KSEA: one under the cap, one asked for with `limit: 10` so the page comes back
 * full. The mock holds only the first request of a capped walk, so the whole walk runs
 * against a fake service answering from the recorded span the way the recordings show the
 * service answers.
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { beforeAll, describe, expect, expectTypeOf, inject, it } from 'vitest'
import type { HttpCall, HttpEndpoint, PaginatedResponse, SeekState, TimestampIso } from '@truewire/core'
import { Weather } from '../src/weather-gov/core/index.js'
import type { DefaultMeta } from '../src/weather-gov/meta.js'
import { GetObservations } from '../src/weather-gov/stations/get_observations.js'
import type { ObservationFeature } from '../src/weather-gov/types/index.js'
import { projectRoot } from './setup.js'

const EXAMPLES = path.join(projectRoot, 'spec/endpoints/stations/get_observations/examples')

interface Span { station_id: string; start: string; end: string; limit: number }
interface Row { id: string; properties: { timestamp: string } }

/**
 * The request half of one recorded example, read rather than written here: the service
 * keeps about a week of observations, so `test/refresh_examples.py` moves both spans
 * forward before every re-recording.
 */
function recorded(example: string): Span {
  return (JSON.parse(readFileSync(path.join(EXAMPLES, `${example}.request.json`), 'utf8')) as { request: Span }).request
}

function observations(example: string): Row[] {
  const file = path.join(EXAMPLES, `${example}.response.json`)
  return (JSON.parse(readFileSync(file, 'utf8')) as { payload: { features: Row[] } }).payload.features
}

const WINDOW = recorded('ksea_window')
const CAPPED = recorded('ksea_capped')
const START = new Date(WINDOW.start)
const END = new Date(WINDOW.end)
const CAP = CAPPED.limit

/** What the six hours actually hold, newest first. */
const ROWS = observations('ksea_window')
const at = (row: Row): number => Date.parse(row.properties.timestamp)
const ids = (rows: readonly { id: string }[]): string[] => rows.map(row => row.id)

let client: Weather

beforeAll(() => {
  client = Weather.new({ contact: 'tests@truewire.dev', baseUrl: inject('httpBaseUrl') })
})

describe('a span under the cap', () => {
  it('is one page', async () => {
    // A second request would 422 from the mock rather than quietly return nothing.
    expect(ROWS.length).toBeLessThan(500)
    const walk = client.stations.getObservationsPaged({ station_id: 'KSEA', start: START, end: END, limit: 500 })
    const pages = []
    for await (const page of walk.pages()) pages.push(page)
    expect(pages).toHaveLength(1)
    expect(pages[0]!.next).toBeNull()
    expect(pages[0]!.rows).toHaveLength(ROWS.length)
  })

  it('awaited, returns every observation newest first', async () => {
    const rows = await client.stations.getObservationsPaged({ station_id: 'KSEA', start: START, end: END, limit: 500 })
    expect(ids(rows)).toEqual(ids(ROWS))
  })
})

describe('a capped page', () => {
  it('keeps the newest rows', () => {
    // The recorded fact `anchor: end` rests on: the capped page is the head of the full one.
    const capped = observations('ksea_capped')
    expect([CAPPED.start, CAPPED.end]).toEqual([WINDOW.start, WINDOW.end])
    expect(capped).toHaveLength(CAP)
    expect(CAP).toBeLessThan(ROWS.length)
    expect(ids(capped)).toEqual(ids(ROWS.slice(0, CAP)))
  })

  it('moves end to the oldest observation it held', async () => {
    const walk = client.stations.getObservationsPaged({ station_id: 'KSEA', start: START, end: END, limit: CAP })
    const [rows, following] = await walk.next(walk.init)
    expect(rows).toHaveLength(CAP)
    expect(following).not.toBeNull()
    const [pos, carried] = following!
    const oldest = observations('ksea_capped').at(-1)!
    expect(pos?.getTime()).toBe(at(oldest))
    expect(ids(carried)).toEqual([oldest.id])
  })
})

/**
 * The service as the recordings show it: newest first, `start` inclusive, `end` exclusive
 * (measured live on 2026-09-28), at most `min(limit, 500)` rows kept from the newest end.
 * Records the `end` each request sent. With `inclusiveEnd`, it re-serves the observation
 * at `end`, which the walk has to drop.
 */
function service(ends: number[], inclusiveEnd = false): HttpEndpoint<DefaultMeta> {
  return {
    async request<Req, Res>(call: HttpCall<Req, Res, DefaultMeta>): Promise<Res> {
      const query = call.requestCodec!.dump(call.request!) as { start?: string; end?: string; limit?: number }
      const low = query.start === undefined ? -Infinity : Date.parse(query.start)
      const high = query.end === undefined ? Infinity : Date.parse(query.end)
      ends.push(high)
      const held = ROWS.filter(row => low <= at(row) && (inclusiveEnd ? at(row) <= high : at(row) < high))
      const body = { type: 'FeatureCollection', features: held.slice(0, Math.min(query.limit ?? 500, 500)) }
      return (call.validate === false ? body : call.responseCodec!.parse(body)) as Res
    },
  }
}

describe('the whole walk', () => {
  it.each([
    ['an exclusive end, as the live service has', false],
    ['an inclusive end, re-serving the boundary', true],
  ])(`at limit ${CAP} against %s, returns every observation once, newest first`, async (_, inclusiveEnd) => {
    const ends: number[] = []
    const walk = new GetObservations(service(ends, inclusiveEnd)).getObservationsPaged({ station_id: 'KSEA', start: START, end: END, limit: CAP })
    const rows = await walk
    expect(ids(rows)).toEqual(ids(ROWS))
    // Every request after the first ends at the oldest observation of the page before it; a
    // re-served boundary observation takes one place in every page after the first.
    const step = inclusiveEnd ? CAP - 1 : CAP
    const oldest = ROWS.filter((_, index) => index >= CAP - 1 && (index - (CAP - 1)) % step === 0).map(at)
    expect(ends).toEqual([END.getTime(), ...oldest])
  })

  it('with validate: false, returns the same rows', async () => {
    const walk = new GetObservations(service([])).getObservationsPaged(
      { station_id: 'KSEA', start: START, end: END, limit: CAP },
      { validate: false },
    )
    expect(ids((await walk) as Row[])).toEqual(ids(ROWS))
  })

  it('resumes from a page it checkpointed', async () => {
    const walk = new GetObservations(service([])).getObservationsPaged({ station_id: 'KSEA', start: START, end: END, limit: 30 })
    const first = await walk.pages().next()
    expect(first.done).toBe(false)
    const page = first.value!
    expect(page.rows).toHaveLength(30)
    const rest = await walk.resume(page.next!)
    expect(ids([...page.rows, ...rest])).toEqual(ids(ROWS))
  })

  it('is typed by what it walks', () => {
    const request = { station_id: 'KSEA', start: START, end: END }
    expectTypeOf(client.stations.getObservationsPaged(request))
      .toEqualTypeOf<PaginatedResponse<ObservationFeature, SeekState<ObservationFeature, TimestampIso>>>()
    expectTypeOf(client.stations.getObservationsPaged(request, { validate: false }))
      .toEqualTypeOf<PaginatedResponse<unknown, SeekState<unknown, TimestampIso>>>()
  })
})
