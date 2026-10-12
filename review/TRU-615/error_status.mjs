// TRU-615: an error the API returns must carry its status and body (ApiError { status, body }),
// and a 422 is a BadRequest. Exits 1 while packages/typescript/src/weather-gov/core/http.ts
// raiseForStatus drops them. Run: (cd packages/typescript && yarn build) && node review/TRU-615/error_status.mjs
import { createServer } from 'node:http'
import { ApiError, BadRequest } from '../../packages/typescript/node_modules/@truewire/core/dist/index.js'
import { Weather } from '../../packages/typescript/dist/core/index.js'

const answers = {
  '/radar/profilers/TLKA2': [404, { title: 'Not Found', status: 404 }],
  '/radar/stations': [503, { title: 'Service Unavailable', detail: 'An upstream data source is temporarily unavailable.', status: 503 }],
  '/radar/queues/rds': [422, { title: 'Unprocessable', status: 422 }],
}
const server = createServer((req, res) => {
  const [status, body] = answers[new URL(req.url, 'http://x').pathname]
  res.writeHead(status, { 'content-type': 'application/problem+json' }).end(JSON.stringify(body))
})
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve))
const client = Weather.new({ contact: 'hello@truewire.dev', baseUrl: `http://127.0.0.1:${server.address().port}` })
let failed = 0
for (const [want, Class, call] of [
  [404, ApiError, () => client.radar.getProfiler({ station_id: 'TLKA2' })],
  [503, ApiError, () => client.radar.listStations({ reportingHost: 'nope' })],
  [422, BadRequest, () => client.radar.getQueue({ host: 'rds' })],
]) {
  try {
    await call()
    console.log(`FAIL ${want}: no error`); failed++
  } catch (err) {
    const ok = err instanceof Class && err.status === want && err.body?.status === want
    console.log(`${ok ? 'ok  ' : 'FAIL'} ${want}: ${err.constructor.name} status=${err.status} body=${JSON.stringify(err.body)}`)
    if (!ok) failed++
  }
}
server.close()
process.exit(failed ? 1 : 0)
