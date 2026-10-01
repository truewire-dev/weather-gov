import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

// Usage: node reviews/TRU-597/wire-probe.mjs /path/to/built/weather-gov
const root = path.resolve(process.argv[2] ?? '.')
const pkg = path.join(root, 'packages/typescript')
const { Weather } = await import(pathToFileURL(path.join(pkg, 'dist/core/index.js')))
const { HttpClient } = await import(pathToFileURL(path.join(pkg, 'node_modules/@truewire/core/dist/index.js')))
const fixture = async (endpoint, example) => JSON.parse(await readFile(
  path.join(root, 'spec/endpoints', endpoint, 'examples', `${example}.response.json`), 'utf8',
)).payload

let expectedPath
let response
let calls = 0
const client = Weather.new({
  contact: 'review@truewire.dev',
  http: new HttpClient({ fetch: async request => {
    const url = new URL(request.url)
    assert.equal(decodeURIComponent(url.pathname), expectedPath)
    assert.equal(request.method, 'GET')
    calls++
    return new Response(JSON.stringify(response), { headers: { 'Content-Type': 'application/json' } })
  } }),
})
async function serve(endpoint, example, pathname) {
  response = await fixture(endpoint, example)
  expectedPath = pathname
}

await serve('stations/get_station', 'ksea', '/stations/KSEA')
const station = await client.stations.getStation({ station_id: 'KSEA' })
assert.deepEqual(station.geometry.coordinates, response.geometry.coordinates)

await serve('stations/get_observation', 'ksea_metar', '/stations/KSEA/observations/2026-09-30T16:53:00Z')
const observation = await client.stations.getObservation({ station_id: 'KSEA', time: new Date('2026-09-30T16:53:00Z') })
assert.equal(observation.timestamp.toISOString(), '2026-09-30T16:53:00.000Z')

await serve('stations/list_tafs', 'ksea', '/stations/KSEA/tafs')
const tafs = await client.stations.listTafs({ station_id: 'KSEA' })
assert.equal(tafs['@graph'].length, response['@graph'].length)
assert.ok(tafs['@graph'].every(taf => taf.issueTime instanceof Date))

await serve('offices/get_briefing', 'seattle', '/offices/SEW/briefing')
assert.equal((await client.offices.getBriefing({ office_id: 'SEW' })).briefing, null)
await serve('offices/get_briefing', 'active', '/offices/AKQ/briefing')
assert.ok((await client.offices.getBriefing({ office_id: 'AKQ' })).briefing.startTime instanceof Date)

await serve('offices/list_headlines', 'wakefield', '/offices/AKQ/headlines')
const headlines = (await client.offices.listHeadlines({ office_id: 'AKQ' }))['@graph']
assert.equal(headlines[0].summary, null)
assert.notEqual(headlines[0]['@id'], headlines[0].id)
await serve('offices/get_headline', 'wakefield', `/offices/AKQ/headlines/${headlines[0].id}`)
const headline = await client.offices.getHeadline({ office_id: 'AKQ', headline_id: headlines[0].id })
assert.equal(headline.id, response.id)
assert.equal(headline['@id'], response['@id'])
assert.equal(headline.summary, null)

await serve('offices/list_weather_stories', 'wakefield', '/offices/AKQ/weatherstories')
const stories = await client.offices.listWeatherStories({ office_id: 'AKQ' })
assert.ok(stories.stories.every(story => story.updateTime instanceof Date))

await serve('radio/get_transmitter', 'seattle', '/radio/KHB60')
assert.equal((await client.radio.getTransmitter({ call_sign: 'KHB60' })).transmitterFrequency, '162.550')

await serve('radio/list_transmitters', 'last_page', '/radio')
const page = await client.radio.listTransmitters()
assert.equal(page['@graph'].length, 228)
assert.equal(page.pagination, undefined)
for (let i = 0; i < 228; i++) {
  assert.equal(page['@graph'][i].transmitterFrequency, response['@graph'][i].transmitterFrequency)
}
assert.deepEqual(await client.radio.listTransmitters(undefined, { validate: false }), response)
assert.equal(calls, 11)
console.log('PASS: nine operations, eleven calls; exact Date path, nulls, distinct IDs, and decimal strings preserved')
