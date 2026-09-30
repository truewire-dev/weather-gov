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
import type {
  PointGeometry,
  PolygonGeometry,
  QuantitativeValue,
  ZoneFeature,
} from '../src/weather-gov/types/index.js'
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
const ZONE_WINDOW = recorded<{ zone_id: string; start: string; end: string; limit: number }>(
  'stations/get_observations_for_zone/examples/seattle_capped.request.json',
)
const ZONE_STATIONS = recorded<{ zone_id: string }>(
  'stations/list_stations_for_zone/examples/seattle.request.json',
)

/** A `QuantitativeValue`: a unit, and a number or an honest null. */
function isMeasurement(value: QuantitativeValue, unit?: string): void {
  expect(value.unitCode.startsWith('wmoUnit:')).toBe(true)
  expect(value.value === null || typeof value.value === 'number').toBe(true)
  if (unit !== undefined) expect(value.unitCode).toBe(unit)
}

/** A GeoJSON point: longitude first, and both inside the globe. */
function isPoint(geometry: PointGeometry | undefined): void {
  expect(geometry?.type).toBe('Point')
  const [longitude, latitude] = geometry!.coordinates
  expect(longitude).toBeGreaterThanOrEqual(-180)
  expect(longitude).toBeLessThanOrEqual(180)
  expect(latitude).toBeGreaterThanOrEqual(-90)
  expect(latitude).toBeLessThanOrEqual(90)
}

/** A zone feature: its URL is its code, and a list leaves the outline out. */
function isZone(feature: ZoneFeature, geometry: boolean): ZoneFeature['properties'] {
  const zone = feature.properties
  expect(feature.type).toBe('Feature')
  expect(feature.id).toBe(zone['@id'])
  expect(zone['@id'].endsWith(`/${zone.id}`)).toBe(true)
  expect(zone.name).toBeTruthy()
  expect(zone.effectiveDate.getTime()).toBeLessThan(zone.expirationDate.getTime())
  if (geometry) expect(['Polygon', 'MultiPolygon']).toContain(feature.geometry?.type)
  else expect(feature.geometry).toBeNull()
  return zone
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

  it('zones.listZones finds one zone of each land kind at a point', async () => {
    const page = await client.zones.listZones({ point: '47.6062,-122.3321' })
    const zones = page.features.map(feature => isZone(feature, false))
    expect(zones.map(zone => zone.type).sort()).toEqual(['county', 'fire', 'public'])
    const ids = zones.map(zone => zone.id)
    expect(ids).toContain('WAZ315')
    expect(ids).toContain('WAC033')
    for (const zone of zones) expect(zone.state).toBe('WA')
  })

  it('zones.listZones honours area, type and limit, ordered by code', async () => {
    const page = await client.zones.listZones({ area: ['WA'], type: ['fire'], limit: 3 })
    const zones = page.features.map(feature => isZone(feature, false))
    expect(zones).toHaveLength(3)
    for (const zone of zones) {
      expect(zone.state).toBe('WA')
      expect(zone.type).toBe('fire')
    }
    const ids = zones.map(zone => zone.id)
    expect([...ids].sort()).toEqual(ids)
  })

  it('zones.listZonesByType takes the type from the path', async () => {
    const page = await client.zones.listZonesByType({
      zone_type: 'county',
      area: ['WA'],
      limit: 5,
    })
    const zones = page.features.map(feature => isZone(feature, false))
    expect(zones).toHaveLength(5)
    for (const zone of zones) {
      expect(zone.type).toBe('county')
      expect(zone.state).toBe('WA')
      expect(zone.id.startsWith('WAC')).toBe(true)
    }
  })

  it('zones.getZone keeps the whole feature, outline included', async () => {
    const feature = await client.zones.getZone({ zone_id: 'WAZ315', zone_type: 'forecast' })
    const zone = isZone(feature, true)
    expect([zone.id, zone.type, zone.name]).toEqual(['WAZ315', 'public', 'City of Seattle'])
    expect(zone.gridIdentifier).toBe('SEW')
    expect(zone.forecastOffice!.endsWith('/offices/SEW')).toBe(true)
    expect(zone.timeZone).toEqual(['America/Los_Angeles'])
    expect(zone.observationStations!.some(url => url.endsWith('/stations/KSEA'))).toBe(true)
    // A polygon's rings close on themselves.
    expect(feature.geometry?.type).toBe('Polygon')
    const ring = (feature.geometry as PolygonGeometry).coordinates[0]!
    expect(ring.length).toBeGreaterThan(3)
    expect(ring.at(-1)).toEqual(ring[0])
  })

  it('zones.getForecast returns the payload: numbered periods of prose', async () => {
    const forecast = await client.zones.getForecast({ zone_id: 'WAZ315', zone_type: 'forecast' })
    expect('properties' in forecast).toBe(false)
    expect(forecast.zone.endsWith('/zones/forecast/WAZ315')).toBe(true)
    expect(forecast.periods.length).toBeGreaterThan(6)
    expect(forecast.periods.map(p => p.number)).toEqual(
      Array.from({ length: forecast.periods.length }, (_, index) => index + 1),
    )
    for (const period of forecast.periods) {
      expect(period.name).toBeTruthy()
      expect(period.detailedForecast).toBeTruthy()
    }
  })

  it('zones.listTransmitters answers in JSON-LD, every one for the county asked', async () => {
    const radio = await client.zones.listTransmitters({ zone_id: 'WAC033', zone_type: 'county' })
    const graph = radio['@graph']
    expect(graph.length).toBeGreaterThan(0)
    for (const transmitter of graph) {
      expect(transmitter.counties).toContain('WAC033')
      expect(transmitter.sameCodes!.length).toBe(transmitter.counties.length)
      // A decimal string on the wire, kept as one: 162.400 to 162.550 MHz.
      expect(Number(transmitter.transmitterFrequency)).toBeGreaterThan(162)
      expect(Number(transmitter.transmitterFrequency)).toBeLessThan(163)
    }
    expect(graph.map(transmitter => transmitter.callSign)).toContain('KHB60')
  })

  it('stations.getObservationsForZone merges stations newest first, capped', async () => {
    const page = await client.stations.getObservationsForZone({
      zone_id: ZONE_WINDOW.zone_id,
      start: new Date(ZONE_WINDOW.start),
      end: new Date(ZONE_WINDOW.end),
      limit: ZONE_WINDOW.limit,
    })
    expect(page.features).toHaveLength(ZONE_WINDOW.limit)
    const times = page.features.map(f => f.properties.timestamp.getTime())
    expect([...times].sort((a, b) => b - a)).toEqual(times)
    for (const time of times) {
      expect(time).toBeGreaterThanOrEqual(Date.parse(ZONE_WINDOW.start))
      expect(time).toBeLessThan(Date.parse(ZONE_WINDOW.end))
    }
    expect(new Set(page.features.map(f => f.properties.stationId)).size).toBeGreaterThan(1)
    // Timestamps repeat across stations: why this endpoint declares no seek walk.
    expect(new Set(times).size).toBeLessThan(times.length)
    for (const feature of page.features) {
      isPoint(feature.geometry)
      isMeasurement(feature.properties.temperature)
    }
  })

  it('stations.listStationsForZone lists the stations the zone names', async () => {
    const page = await client.stations.listStationsForZone({ zone_id: ZONE_STATIONS.zone_id })
    expect(page.features.length).toBeGreaterThan(0)
    for (const feature of page.features) {
      isPoint(feature.geometry)
      expect(feature.properties.stationIdentifier).toBeTruthy()
    }
    const urls = page.features.map(feature => feature.id)
    expect(page.observationStations).toEqual(urls)
    const zone = (
      JSON.parse(
        readFileSync(
          path.join(projectRoot, 'spec/endpoints/zones/get_zone/examples/seattle.response.json'),
          'utf8',
        ),
      ) as { payload: { properties: { id: string; observationStations: string[] } } }
    ).payload.properties
    expect(zone.id).toBe(ZONE_STATIONS.zone_id)
    expect([...urls].sort()).toEqual([...zone.observationStations].sort())
  })

  it('stations.listStationsForGridpoint answers nearest first, with distance and bearing', async () => {
    const page = await client.stations.listStationsForGridpoint({
      office: 'SEW',
      grid_x: 125,
      grid_y: 68,
      limit: 5,
    })
    expect(page.features).toHaveLength(5)
    const distances = page.features.map(feature => {
      isMeasurement(feature.properties.distance!, 'wmoUnit:m')
      isMeasurement(feature.properties.bearing!, 'wmoUnit:degree_(angle)')
      return feature.properties.distance!.value as number
    })
    expect([...distances].sort((a, b) => a - b)).toEqual(distances)
  })
})
