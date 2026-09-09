/**
 * Every recorded example replayed through the generated TypeScript client against
 * `truewire mock`, which serves the same recordings over real HTTP. Nothing here touches
 * the network.
 *
 * The assertions are the TypeScript half of `packages/python/test/test_recordings.py`:
 * structural, not literal, because the counts and the text move with every re-recording
 * and the shape does not. Where Python proves a thing about a response, this proves the
 * same thing about the same response, so a divergence between the two clients is a test
 * failure rather than a discovery months later.
 */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { beforeAll, describe, expect, inject, it } from 'vitest'
import { Weather } from '../src/weather-gov/core/index.js'
import type { QuantitativeValue } from '../src/weather-gov/types/index.js'
import { projectRoot } from './setup.js'

const CONTACT = 'tests@truewire.dev'

/** The request half of one recorded example: the source of truth for what to replay. */
function recorded<T>(file: string): T {
  const full = path.join(projectRoot, 'spec/endpoints', file)
  return (JSON.parse(readFileSync(full, 'utf8')) as { request: T }).request
}

const WINDOW = recorded<{ station_id: string; start: string; end: string; limit: number }>(
  'stations/get_observations/examples/ksea_window.request.json',
)
const ALERT = recorded<{ id: string }>('alerts/get_alert/examples/one.request.json')

/** A `QuantitativeValue`: a unit, and a number or an honest null. */
function isMeasurement(value: QuantitativeValue, unit?: string): void {
  expect(value.unitCode.startsWith('wmoUnit:')).toBe(true)
  expect(value.value === null || typeof value.value === 'number').toBe(true)
  if (unit !== undefined) expect(value.unitCode).toBe(unit)
}

let client: Weather

beforeAll(() => {
  client = Weather.new({ contact: CONTACT, baseUrl: inject('httpBaseUrl') })
})

describe('recorded examples replay through the generated client', () => {
  it('points.getPoint returns the payload, not the GeoJSON wrapper', async () => {
    const point = await client.points.getPoint({ latitude: 47.6062, longitude: -122.3321 })
    expect(point.gridId).toBe('SEW')
    expect(point.gridX).toBe(125)
    expect(point.gridY).toBe(68)
    expect(point.timeZone).toBe('America/Los_Angeles')
    // The declared envelope, working: no `properties` to reach through.
    expect('properties' in point).toBe(false)
    const nearest = point.relativeLocation!.properties
    expect(nearest.city).toBe('Seattle')
    expect(nearest.state).toBe('WA')
  })

  it('forecast.getForecast returns fourteen periods of prose', async () => {
    const forecast = await client.forecast.getForecast({ office: 'SEW', grid_x: 125, grid_y: 68 })
    expect(forecast.periods).toHaveLength(14)
    expect(forecast.units).toBe('us')
    expect(forecast.periods.map(p => p.number)).toEqual(
      Array.from({ length: 14 }, (_, index) => index + 1),
    )
    for (const period of forecast.periods) {
      // The one place this API sends a bare number beside a unit *string*.
      expect(typeof period.temperature).toBe('number')
      expect(period.temperatureUnit).toBe('F')
      expect(period.shortForecast).toBeTruthy()
      isMeasurement(period.probabilityOfPrecipitation!, 'wmoUnit:percent')
    }
  })

  it('forecast.getHourlyForecast fills what the narrative one leaves out', async () => {
    const hourly = await client.forecast.getHourlyForecast({
      office: 'SEW',
      grid_x: 125,
      grid_y: 68,
    })
    expect(hourly.periods.length).toBeGreaterThan(100)
    const first = hourly.periods[0]!
    expect(first.name).toBe('')
    expect(first.detailedForecast).toBe('')
    isMeasurement(first.dewpoint!, 'wmoUnit:degC')
    isMeasurement(first.relativeHumidity!, 'wmoUnit:percent')
  })

  it('forecast.getGridData returns the raw series behind both forecasts', async () => {
    const grid = await client.forecast.getGridData({ office: 'SEW', grid_x: 125, grid_y: 68 })
    expect(grid.gridId).toBe('SEW')
    const temperature = grid.temperature!
    expect(temperature.uom!.startsWith('wmoUnit:')).toBe(true)
    expect(temperature.values.length).toBeGreaterThan(20)
    for (const entry of temperature.values.slice(0, 5)) {
      // A `validTime` is an interval, not an instant: `<start>/<duration>`.
      const [start, duration] = entry.validTime.split('/')
      expect(start).toBeTruthy()
      expect(duration!.startsWith('P')).toBe(true)
    }
  })

  it('stations.listStations sends a repeated query key, not a stringified array', async () => {
    const page = await client.stations.listStations({ state: ['WA'], limit: 20 })
    expect(page.type).toBe('FeatureCollection')
    expect(page.features).toHaveLength(20)
    for (const feature of page.features) {
      expect(feature.geometry!.type).toBe('Point')
      expect(feature.properties.stationIdentifier).toBeTruthy()
    }
    expect(page.pagination!.next!.startsWith('https://api.weather.gov/stations?')).toBe(true)
  })

  it('stations.getLatestObservation carries a unit on every measurement', async () => {
    const observation = await client.stations.getLatestObservation({ station_id: 'KSEA' })
    expect(observation.stationId).toBe('KSEA')
    isMeasurement(observation.temperature, 'wmoUnit:degC')
    isMeasurement(observation.dewpoint, 'wmoUnit:degC')
    isMeasurement(observation.windSpeed, 'wmoUnit:km_h-1')
    // A null measurement is normal, not an error: there is no gust unless it gusted.
    expect(observation.windGust !== undefined).toBe(true)
    for (const layer of observation.cloudLayers) {
      expect(['OVC', 'BKN', 'SCT', 'FEW', 'SKC', 'CLR', 'VV']).toContain(layer.amount)
      isMeasurement(layer.base, 'wmoUnit:m')
    }
  })

  it('stations.getObservations answers newest first', async () => {
    const page = await client.stations.getObservations({
      station_id: WINDOW.station_id,
      // The generated request types the bounds as `Date`, not as the ISO strings the wire
      // carries -- so a caller works in dates and the codec renders them back.
      start: new Date(WINDOW.start),
      end: new Date(WINDOW.end),
      limit: WINDOW.limit,
    })
    const timestamps = page.features.map(f => f.properties.timestamp)
    expect(page.features.length).toBeGreaterThan(0)
    expect(page.features.length).toBeLessThan(500)
    expect([...timestamps].sort().reverse()).toEqual(timestamps)
  })

  it('alerts.getActiveAlerts honours filters that disagree about capitalisation', async () => {
    const page = await client.alerts.getActiveAlerts({ status: ['actual'], severity: ['Severe'] })
    expect(page.features.length).toBeGreaterThan(0)
    for (const feature of page.features) {
      expect(feature.properties.severity).toBe('Severe')
      expect(feature.properties.status).toBe('Actual')
      expect(feature.properties.id.startsWith('urn:oid:')).toBe(true)
    }
  })

  it('alerts.getAlert keeps the whole feature, because its geometry is real data', async () => {
    const alert = await client.alerts.getAlert({ id: ALERT.id })
    expect(alert.type).toBe('Feature')
    expect(alert.properties.id).toBe(ALERT.id)
    // The identifier is `urn:oid:...`, so this also proves `:` survived the path unencoded.
    expect(ALERT.id).toContain(':')
    if (alert.geometry !== null && alert.geometry !== undefined) {
      expect(['Polygon', 'MultiPolygon']).toContain(alert.geometry.type)
    }
  })

  it('offices.getOffice answers in schema.org, not GeoJSON', async () => {
    const office = await client.offices.getOffice({ office_id: 'SEW' })
    expect(office.id).toBe('SEW')
    expect(office.address!.addressRegion).toBe('WA')
    expect(office.responsibleForecastZones!.length).toBeGreaterThan(0)
  })

  it('products.listProductTypes answers in JSON-LD, a third vocabulary again', async () => {
    const types = await client.products.listProductTypes({})
    expect(types['@graph'].length).toBeGreaterThan(300)
    const codes = new Set(types['@graph'].map(entry => entry.productCode))
    expect(codes.has('AFD')).toBe(true)
    expect(codes.has('TOR')).toBe(true)
  })
})
