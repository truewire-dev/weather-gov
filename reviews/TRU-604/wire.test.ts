import { readFileSync } from 'node:fs'
import { HttpClient, DateIso } from '@truewire/core'
import { expect, it } from 'vitest'
import { Weather, AdvisoryPolygon, AdvisoryPosition, SigmetFeature, CenterWeatherAdvisoryFeature } from '../../packages/typescript/src/weather-gov/core/index.js'

const example = (file: string) => JSON.parse(readFileSync(new URL('../../spec/endpoints/aviation/' + file, import.meta.url), 'utf8')).payload
const sigmets = example('list_sigmets/examples/convective_1e.response.json')
const client = Weather.new({ contact: 'review@example.com', http: new HttpClient({
  fetch: async () => new Response(JSON.stringify(sigmets), { headers: { 'content-type': 'application/geo+json' } }),
}) })

it('demonstrates a Date operation accepted by tsc crashing on recorded raw JSON', async () => {
  const raw = await client.aviation.listSigmets(undefined, { validate: false })
  expect(typeof raw.features[0].properties.issueTime).toBe('string')
  expect(() => raw.features[0].properties.issueTime.toISOString()).toThrow(TypeError)
  const validated = await client.aviation.listSigmets()
  expect(validated.features[0].properties.issueTime).toBeInstanceOf(Date)
  console.log('raw omitted request: string timestamp; typed toISOString() throws TypeError; validated control: Date')
})

it('preserves tuple coordinates, unwrapped longitude and explicit nulls', () => {
  const body = example('get_sigmet/examples/anchorage_latest.response.json')
  const feature = SigmetFeature.parse(body)
  expect(feature.type).toBe('Feature')
  expect(feature.geometry!.coordinates).toEqual(body.geometry.coordinates)
  expect(feature.geometry!.coordinates.flat().some(([lat, lon]) => lat > 0 && lon < -180)).toBe(true)
  expect(feature.properties.fir).toBeNull()
  expect(feature.properties.issueTime).toBeInstanceOf(Date)
  expect(SigmetFeature.dump(feature)).toMatchObject({ properties: { issueTime: expect.any(String) } })
  expect(SigmetFeature.parse({ ...body, geometry: null, properties: { ...body.properties, fir: null, sequence: null, phenomenon: null } }).geometry).toBeNull()
  const cwa = example('get_cwa/examples/latest.response.json')
  expect(CenterWeatherAdvisoryFeature.parse({ ...cwa, geometry: null, properties: { ...cwa.properties, observedProperty: null } }).properties.observedProperty).toBeNull()
  for (const invalid of [[53], [53, -190, 1], ['53', -190]]) expect(() => AdvisoryPosition.parse(invalid)).toThrow()
  expect(AdvisoryPosition.parse([53, -190])).toEqual([53, -190])
  expect(AdvisoryPolygon.parse(body.geometry).coordinates).toEqual(body.geometry.coordinates)
})

it('serializes UTC dates, leading-zero HHMM and only supplied filters', async () => {
  const requests: URL[] = []
  const single = example('get_sigmet/examples/anchorage_latest.response.json')
  const capture = Weather.new({ contact: 'review@example.com', http: new HttpClient({ fetch: async request => {
    requests.push(new URL(request instanceof Request ? request.url : String(request)))
    return new Response(JSON.stringify(requests.length === 1 ? single : sigmets))
  } }) })
  await capture.aviation.getSigmet({ atsu: 'ANC', date: DateIso.of('2026-09-30'), time: '0055' })
  expect(requests[0].pathname).toBe('/aviation/sigmets/ANC/2026-09-30/0055')
  await capture.aviation.listSigmets({ date: DateIso.of('2026-09-30'), start: new Date('2026-09-30T00:55:00Z'), sequence: '1E' })
  expect([...requests[1].searchParams.keys()].sort()).toEqual(['date', 'sequence', 'start'])
  expect(requests[1].searchParams.get('date')).toBe('2026-09-30')
  expect(requests[1].searchParams.get('sequence')).toBe('1E')
  await capture.aviation.listSigmets()
  expect(requests[2].search).toBe('')
})
