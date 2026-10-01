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
const SPGDS = recorded<{ published: string }>('radar/list_spgds/examples/one_minute.request.json')
const QUEUE = recorded<{ host: 'rds' | 'tds'; station: string; arrived: string; limit: number }>(
  'radar/get_queue/examples/seattle_capped.request.json',
)

/** The start and end of a `start/duration` ISO 8601 interval, such as `2026-09-30T23:00:00Z/PT10M`. */
function interval(value: string): [number, number] {
  const [start, duration] = value.split('/')
  const match = /^PT(?:(\d+)H)?(?:(\d+)M)?$/.exec(duration!)
  expect(match).not.toBeNull()
  const minutes = Number(match![1] ?? 0) * 60 + Number(match![2] ?? 0)
  const from = Date.parse(start!)
  return [from, from + minutes * 60_000]
}

/** A ping group: target name to whether it answered, or `[]` when there are none. */
function isPingGroup(group: Record<string, boolean> | boolean[]): void {
  if (Array.isArray(group)) expect(group).toEqual([])
  else for (const answered of Object.values(group)) expect(typeof answered).toBe('boolean')
}

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
    expect(point.forecast.endsWith('/gridpoints/SEW/125,68/forecast')).toBe(true)
    // The declared envelope, working: no `properties` to reach through.
    expect('properties' in point).toBe(false)
    const nearest = point.relativeLocation!.properties
    expect(nearest.city).toBe('Seattle')
    expect(nearest.state).toBe('WA')
    isMeasurement(nearest.distance!, 'wmoUnit:m')
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
    const weather = grid.weather!.values[0]!.value
    expect(Array.isArray(weather)).toBe(true)
    for (const phenomenon of weather) {
      for (const key of ['coverage', 'weather', 'intensity']) expect(phenomenon).toHaveProperty(key)
    }
  })

  it('stations.listStations sends a repeated query key, not a stringified array', async () => {
    const page = await client.stations.listStations({ state: ['WA'], limit: 20 })
    expect(page.type).toBe('FeatureCollection')
    expect(page.features).toHaveLength(20)
    for (const feature of page.features) {
      isPoint(feature.geometry)
      expect(feature.properties.stationIdentifier).toBeTruthy()
      expect(feature.properties.name).toBeTruthy()
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
    const timestamps = page.features.map(f => f.properties.timestamp.getTime())
    expect(page.features.length).toBeGreaterThan(0)
    expect(page.features.length).toBeLessThan(500)
    expect([...timestamps].sort((a, b) => b - a)).toEqual(timestamps)
    for (const feature of page.features) {
      isPoint(feature.geometry)
      isMeasurement(feature.properties.temperature)
    }
  })

  it('alerts.getActiveAlerts honours filters that disagree about capitalisation', async () => {
    const page = await client.alerts.getActiveAlerts({ status: ['actual'], severity: ['Severe'] })
    expect(page.features.length).toBeGreaterThan(0)
    for (const feature of page.features) {
      expect(feature.properties.severity).toBe('Severe')
      expect(feature.properties.status).toBe('Actual')
      expect(feature.properties.id.startsWith('urn:oid:')).toBe(true)
      expect(feature.properties.event).toBeTruthy()
      expect(feature.properties.description).toBeTruthy()
      // An alert covers zones or a polygon, never neither.
      expect(feature.geometry != null || feature.properties.affectedZones!.length > 0).toBe(true)
    }
  })

  it('alerts.getAlert keeps the whole feature, because its geometry is real data', async () => {
    const alert = await client.alerts.getAlert({ id: ALERT.id })
    expect(alert.type).toBe('Feature')
    expect(alert.properties.id).toBe(ALERT.id)
    expect(alert.properties.severity).toBe('Severe')
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
    expect(office.approvedObservationStations!.length).toBeGreaterThan(0)
  })

  it('products.listProductTypes answers in JSON-LD, a third vocabulary again', async () => {
    const types = await client.products.listProductTypes({})
    expect(types['@graph'].length).toBeGreaterThan(300)
    const codes = new Set(types['@graph'].map(entry => entry.productCode))
    expect(codes.has('AFD')).toBe(true)
    expect(codes.has('TOR')).toBe(true)
    for (const entry of types['@graph']) expect(entry.productName).toBeTruthy()
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
  it('radar.listServers lists the LDM servers and the distribution hosts, empty groups as []', async () => {
    const page = await client.radar.listServers()
    const servers = new Map(page['@graph'].map(server => [server.id, server]))
    for (const name of ['ldm1', 'rds', 'tds']) expect(servers.has(name)).toBe(true)
    for (const [name, server] of servers) {
      expect(server['@id'].endsWith(`/radar/servers/${name}`)).toBe(true)
      expect(server.collectionTime).toBeInstanceOf(Date)
      for (const group of Object.values(server.ping.targets)) isPingGroup(group)
      if (server.type === 'ldm') {
        expect(typeof server.active).toBe('boolean')
        expect(server.command?.lastExecutedTime).toBeInstanceOf(Date)
      } else {
        expect(server.command).toBeUndefined()
        expect(server.active).toBeUndefined()
      }
    }
    expect(servers.get('rds')!.ping.targets['radar']).toEqual([])
  })

  it('radar.getServer returns one LDM server, its uptime a boot time', async () => {
    const server = await client.radar.getServer({ server_id: 'ldm1' })
    expect(server.id).toBe('ldm1')
    expect(server.type).toBe('ldm')
    expect(server.ldm.count).toBeGreaterThan(0)
    expect(server.ldm.oldestProduct.getTime()).toBeLessThanOrEqual(server.ldm.latestProduct.getTime())
    expect(server.hardware.uptime.getTime()).toBeLessThan(server.collectionTime.getTime())
    expect(server.network.eth0.interface).toBe('eth0')
    const radars = server.ping.targets['radar'] as Record<string, boolean>
    expect(typeof radars['KATX']).toBe('boolean')
  })

  it('radar.listSpgds parses the Unix seconds and counts the service sends as strings', async () => {
    const [start, end] = interval(SPGDS.published)
    const page = await client.radar.listSpgds({ published: SPGDS.published })
    const reports = page['@graph']
    expect(reports.length).toBeGreaterThan(0)
    for (const report of reports) {
      expect(report.timestamp.getTime()).toBeGreaterThanOrEqual(start)
      expect(report.timestamp.getTime()).toBeLessThanOrEqual(end)
      for (const block of [report.dataflow, report.connectQ, report.appRunning]) {
        expect(block.stateSince).toBeInstanceOf(Date)
        expect(block.stateSince.getTime()).toBeLessThanOrEqual(block.stateValid.getTime())
      }
      expect(typeof report.ldm.conns).toBe('bigint')
      expect(report.secondHD.pctUsed).toBeLessThanOrEqual(100n)
      expect(Number(report.throughput.in)).toBeGreaterThanOrEqual(0)
      expect(report.spgdsUpSince.upSince.getTime()).toBeLessThan(report.timestamp.getTime())
      const sites = Object.values(report.spg)
      expect(sites.length).toBeGreaterThan(0)
      for (const site of sites) expect(site.ldmPingStateSince).toBeInstanceOf(Date)
    }
    const times = reports.map(report => report.timestamp.getTime())
    expect([...times].sort((a, b) => b - a)).toEqual(times)
  })

  it('radar.listStations narrows to the profilers, whose status and latency are null', async () => {
    const page = await client.radar.listStations({ stationType: ['Profiler'] })
    expect(page.features.length).toBeGreaterThan(0)
    for (const feature of page.features) {
      const radar = feature.properties
      expect(radar.stationType).toBe('Profiler')
      expect(feature.id).toBe(radar['@id'])
      isPoint(feature.geometry)
      expect(radar.rda).toBeNull()
      for (const value of Object.values(radar.latency)) expect(value).toBeNull()
      expect(radar.performance).toBeUndefined()
      expect(radar.adaptation).toBeUndefined()
    }
  })

  it('radar.getStation returns the whole feature, with its maintenance reports', async () => {
    const feature = await client.radar.getStation({ station_id: 'KATX' })
    const radar = feature.properties
    expect(radar.id).toBe('KATX')
    expect(radar.stationType).toBe('WSR-88D')
    expect(feature.id).toBe(radar['@id'])
    isPoint(feature.geometry)
    expect(radar.latency.current?.unitCode).toBe('nwsUnit:s')
    expect(radar.latency.levelTwoLastReceivedTime).toBeInstanceOf(Date)
    expect(radar.rda?.properties.volumeCoveragePattern).toBeTruthy()
    for (const report of [radar.performance, radar.adaptation]) {
      const readings = report?.properties
      expect(Array.isArray(readings)).toBe(false)
      const measured = Object.values(readings as object).filter(r => typeof r === 'object')
      expect(measured.length).toBeGreaterThan(0)
      for (const reading of measured) expect(reading).toHaveProperty('unitCode')
    }
    const readings = radar.performance!.properties as Record<string, unknown>
    expect((readings['transmitterPeakPower'] as QuantitativeValue).unitCode).toBe('wmoUnit:kW')
  })

  it('radar.listStationAlarms returns the radar\'s log, newest first', async () => {
    const log = await client.radar.listStationAlarms({ station_id: 'KATX' })
    const alarms = log['@graph']
    expect(alarms.length).toBeGreaterThan(0)
    expect(log['@id']?.endsWith('/radar/stations/KATX/alarms')).toBe(true)
    for (const alarm of alarms) {
      expect(alarm.stationId).toBe('KATX')
      expect(alarm.message).toBeTruthy()
    }
    const times = alarms.map(alarm => alarm.timestamp.getTime())
    expect([...times].sort((a, b) => b - a)).toEqual(times)
  })

  it('radar.getQueue keeps the oldest products from the start of the window', async () => {
    const [start, end] = interval(QUEUE.arrived)
    const queue = await client.radar.getQueue(QUEUE)
    const products = queue['@graph']
    expect(products).toHaveLength(QUEUE.limit)
    const arrivals = products.map(product => product.arrivalTime.getTime())
    expect([...arrivals].sort((a, b) => a - b)).toEqual(arrivals)
    for (const product of products) {
      expect(product.host).toBe(QUEUE.host)
      expect(product.stationId).toBe(QUEUE.station)
      expect(product.arrivalTime.getTime()).toBeGreaterThanOrEqual(start)
      expect(product.arrivalTime.getTime()).toBeLessThan(end)
      expect(product.creationTime.getTime()).toBeLessThanOrEqual(product.arrivalTime.getTime())
      expect(product.size).toBeGreaterThan(0)
    }
  })
})
