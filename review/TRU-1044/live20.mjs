import { Weather } from '../../packages/typescript/dist/core/index.js'
const c = Weather.new({ contact: 'hello@truewire.dev' })
const r = c.radar
async function run(name, f) {
  try { const v = await f(); console.log('OK ', name, v) } catch (e) { console.log('ERR', name, e.constructor.name, String(e.message).slice(0, 300)) }
}
let stations
await run('listStations', async () => { stations = await r.listStations(); return stations.features.length })
await run('listStations two types', async () => { const s = await r.listStations({ stationType: ['TDWR', 'Profiler'] }); return [...new Set(s.features.map(f => f.properties.stationType))] })
await run('listServers', async () => (await r.listServers())['@graph'].length)
for (const h of ['rdss', 'tdss']) await run('listServers ' + h, async () => (await r.listServers({ reportingHost: h }))['@graph'].length)
await run('getServer ldm1', async () => Object.keys(await r.getServer({ server_id: 'ldm1' })).length)
await run('getQueue rds', async () => { const q = await r.getQueue({ host: 'rds', limit: 50 }); return [q['@graph'].length, q['@graph'][0]?.arrivalTime instanceof Date] })
await run('getQueue tds', async () => (await r.getQueue({ host: 'tds', limit: 50 }))['@graph'].length)
await run('listSpgds', async () => (await r.listSpgds())['@graph']?.length ?? 'n/a')
// every station, get + alarms
const ids = stations.features.map(f => f.properties.id)
const kinds = Object.fromEntries(stations.features.map(f => [f.properties.id, f.properties.stationType]))
let ok = 0, bad = {}
for (const id of ids) {
  for (const [n, f] of [['getStation', () => r.getStation({ station_id: id })], ['alarms', () => r.listStationAlarms({ station_id: id })]]) {
    try { await f(); ok++ } catch (e) { const k = `${n} ${kinds[id]} ${e.constructor.name} ${String(e.message).slice(0, 120)}`; (bad[k] ??= []).push(id) }
  }
}
console.log('stations', ids.length, 'ok calls', ok)
for (const [k, v] of Object.entries(bad)) console.log('  ', v.length, k, v.slice(0, 5).join(','))
if (r.getProfiler) {
  const profs = ids.filter(id => kinds[id] === 'Profiler')
  let pok = 0, pbad = {}
  for (const id of profs) { try { await r.getProfiler({ station_id: id }); pok++ } catch (e) { const k = `${e.constructor.name} ${String(e.message).slice(0, 160)}`; (pbad[k] ??= []).push(id) } }
  console.log('profilers', profs.length, 'ok', pok); for (const [k, v] of Object.entries(pbad)) console.log('  ', v.length, k, v.slice(0, 5).join(','))
}
