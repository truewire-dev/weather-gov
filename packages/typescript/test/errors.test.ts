/**
 * The RFC 7807 error mapping in `src/weather-gov/core/http.ts`: an error the service answers
 * carries its status and decoded body, so a caller branches on `err.status` rather than on
 * the message, and a 422 is a `BadRequest` like a 400.
 *
 * The recordings hold no error answers, so a local server answers each path with the
 * problem detail the service sends.
 */
import { createServer, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { ApiError, BadRequest, RateLimited } from '@truewire/core'
import { Weather } from '../src/weather-gov/core/index.js'

const ANSWERS: Record<string, [number, string]> = {
  '/radar/profilers/TLKA2': [404, JSON.stringify({ title: 'Not Found', status: 404 })],
  '/radar/stations': [503, JSON.stringify({
    title: 'Service Unavailable',
    detail: 'An upstream data source is temporarily unavailable.',
    status: 503,
  })],
  '/radar/queues/rds': [422, JSON.stringify({ title: 'Unprocessable', status: 422 })],
  '/radar/servers/bad': [400, JSON.stringify({
    title: 'Bad Request',
    status: 400,
    parameterErrors: [{ parameter: 'host', message: 'Does not match' }],
  })],
  '/radar/servers/busy': [429, JSON.stringify({ title: 'Too Many Requests', status: 429 })],
  '/radar/servers/html': [500, '<html>Internal Server Error</html>'],
}

let server: Server
let client: Weather

beforeAll(async () => {
  server = createServer((req, res) => {
    const [status, body] = ANSWERS[new URL(req.url ?? '/', 'http://x').pathname] ?? [599, '']
    res.writeHead(status, { 'content-type': 'application/problem+json' }).end(body)
  })
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve))
  const { port } = server.address() as AddressInfo
  client = Weather.new({ contact: 'hello@truewire.dev', baseUrl: `http://127.0.0.1:${port}` })
})

afterAll(() => new Promise<void>(resolve => server.close(() => resolve())))

/** The error a call rejects with; fails the test if it resolves. */
async function failure(call: () => Promise<unknown>): Promise<ApiError> {
  try {
    await call()
  } catch (err) {
    expect(err).toBeInstanceOf(ApiError)
    return err as ApiError
  }
  throw new Error('the call resolved; an error answer must reject')
}

describe('raiseForStatus', () => {
  it('a 404 carries its status and body', async () => {
    const err = await failure(() => client.radar.getProfiler({ station_id: 'TLKA2' }))
    expect(err).not.toBeInstanceOf(BadRequest)
    expect(err.status).toBe(404)
    expect(err.body).toEqual({ title: 'Not Found', status: 404 })
    expect(err.message).toBe('GET /radar/profilers/TLKA2: HTTP 404: Not Found')
  })

  it('a 503 carries its status and body', async () => {
    const err = await failure(() => client.radar.listStations({ reportingHost: 'nope' }))
    expect(err.status).toBe(503)
    expect(err.body).toMatchObject({ status: 503, title: 'Service Unavailable' })
    expect(err.message).toContain('An upstream data source is temporarily unavailable.')
  })

  it('a 422 is a BadRequest', async () => {
    const err = await failure(() => client.radar.getQueue({ host: 'rds' }))
    expect(err).toBeInstanceOf(BadRequest)
    expect(err.status).toBe(422)
    expect(err.body).toEqual({ title: 'Unprocessable', status: 422 })
  })

  it('a 400 is a BadRequest led by its parameter errors', async () => {
    const err = await failure(() => client.radar.getServer({ server_id: 'bad' }))
    expect(err).toBeInstanceOf(BadRequest)
    expect(err.status).toBe(400)
    expect(err.message).toBe('GET /radar/servers/bad: HTTP 400: host: Does not match')
  })

  it('a 429 is RateLimited with its status', async () => {
    const err = await failure(() => client.radar.getServer({ server_id: 'busy' }))
    expect(err).toBeInstanceOf(RateLimited)
    expect(err.status).toBe(429)
  })

  it('a body that is not JSON leaves body undefined and keeps the status', async () => {
    const err = await failure(() => client.radar.getServer({ server_id: 'html' }))
    expect(err.status).toBe(500)
    expect(err.body).toBeUndefined()
  })
})
