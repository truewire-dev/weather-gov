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
import { DateIso, type RadarHost, Weather } from '../src/weather-gov/core/index.js'
import type {
  AdvisoryPolygon,
  PointGeometry,
  PolygonGeometry,
  Product,
  QuantitativeValue,
  SigmetFeature,
  ZoneFeature,
} from '../src/weather-gov/types/index.js'
import { projectRoot } from './setup.js'

const CONTACT = 'tests@truewire.dev'

/** The request half of one recorded example: the source of truth for what to replay. */
function recorded<T>(file: string): T {
  const full = path.join(projectRoot, 'spec/endpoints', file)
  return (JSON.parse(readFileSync(full, 'utf8')) as { request: T }).request
}
const PRODUCTS = recorded<{ type: string[]; start: string; end: string; limit: number }>(
  'products/list_products/examples/afd_window.request.json',
)
const PRODUCT = recorded<{ product_id: string }>('products/get_product/examples/seattle_afd.request.json')
const PRODUCT_TYPE = recorded<{ type_id: string }>(
  'products/list_products_by_type/examples/admin_messages.request.json',
)

/** A product list: header fields only, all of one type, newest first. */
function isProductList(products: Product[], code: string, office?: string): void {
  expect(products.length).toBeGreaterThan(0)
  for (const product of products) {
    expect(product['@id'].endsWith(`/products/${product.id}`)).toBe(true)
    expect(product.productCode).toBe(code)
    expect(product.productName).toBeTruthy()
    expect(product.productText).toBeUndefined()
    if (office !== undefined) expect(product.issuingOffice).toBe(office)
  }
  const issued = products.map(product => product.issuanceTime.getTime())
  expect([...issued].sort((a, b) => b - a)).toEqual(issued)
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
const CWA = recorded<{ cwsu_id: 'ZFW'; date: string; sequence: number }>(
  'aviation/get_cwa/examples/latest.request.json',
)
const SIGMET = recorded<{ atsu: string; date: string; time: string }>(
  'aviation/get_sigmet/examples/anchorage_latest.request.json',
)
const SIGMETS_ON_DATE = recorded<{ atsu: string; date: string }>(
  'aviation/list_sigmets_for_atsu_on_date/examples/anchorage.request.json',
)

/** The ids a recorded collection holds, for a test that checks one recording against another. */
function recordedIds(file: string): string[] {
  const full = path.join(projectRoot, 'spec/endpoints', file)
  const payload = (JSON.parse(readFileSync(full, 'utf8')) as {
    payload: { features: { properties: { id: string } }[] }
  }).payload
  return payload.features.map(feature => feature.properties.id)
}

type Box = { latitude: [number, number]; longitude: [number, number] }
/** Fort Worth Center's airspace, generously: north Texas and its neighbours. */
const FORT_WORTH: Box = { latitude: [25, 40], longitude: [-112, -88] }
/** Alaska, with the Aleutians past the antimeridian: the service does not wrap -190 to 170. */
const ALASKA: Box = { latitude: [45, 75], longitude: [-200, -125] }
/**
 * The eastern third of the contiguous US and the waters off it, where the `E` convective
 * SIGMETs are issued; Miami's oceanic airspace reaches 12 N in the Caribbean.
 */
const EAST: Box = { latitude: [5, 50], longitude: [-100, -60] }

/**
 * An aviation outline: a closed polygon, latitude first -- the reverse of every other
 * geometry in this API, which the box around the issuing unit's airspace proves.
 */
function isAdvisoryArea(geometry: AdvisoryPolygon | null, box: Box): void {
  expect(geometry?.type).toBe('Polygon')
  for (const ring of geometry!.coordinates) {
    expect(ring.length).toBeGreaterThan(3)
    expect(ring[ring.length - 1]).toEqual(ring[0])
    for (const [latitude, longitude] of ring) {
      expect(latitude).toBeGreaterThan(box.latitude[0])
      expect(latitude).toBeLessThan(box.latitude[1])
      expect(longitude).toBeGreaterThan(box.longitude[0])
      expect(longitude).toBeLessThan(box.longitude[1])
    }
  }
}

function isNewestFirst(features: { properties: { issueTime: Date } }[]): void {
  const issued = features.map(feature => feature.properties.issueTime.getTime())
  expect([...issued].sort((a, b) => b - a)).toEqual(issued)
}

/** `YYYY-MM-DD` and `HHMM` of an instant, in UTC: how a SIGMET's URL names it. */
function utcDay(date: Date): string {
  return date.toISOString().slice(0, 10)
}
function utcMinute(date: Date): string {
  return date.toISOString().slice(11, 16).replace(':', '')
}

/** A message from `atsu`, named by its UTC issue date and minute: the URL `getSigmet` takes. */
function isSigmetOf(feature: SigmetFeature, atsu: string): SigmetFeature['properties'] {
  const sigmet = feature.properties
  expect(sigmet.atsu).toBe(atsu)
  const issued = sigmet.issueTime
  expect(sigmet.id.endsWith(`/sigmets/${atsu}/${utcDay(issued)}/${utcMinute(issued)}`)).toBe(true)
  expect(sigmet.start.getTime()).toBeLessThanOrEqual(sigmet.end.getTime())
  if (feature.geometry !== null) isAdvisoryArea(feature.geometry, ALASKA)
  return sigmet
}

const ALERT_WINDOW = recorded<{ start: string; end: string; status: ['actual']; limit: number }>(
  'alerts/list_alerts/examples/first_page.request.json',
)
const ZONE = recorded<{ zone_id: string }>('alerts/get_active_alerts_for_zone/examples/in_effect.request.json')
const AREA = recorded<{ area: string }>('alerts/get_active_alerts_for_area/examples/in_effect.request.json')
const REGION = recorded<{ region: 'AL' | 'AT' | 'GL' | 'GM' | 'PA' | 'PI' }>(
  'alerts/get_active_alerts_for_region/examples/in_effect.request.json',
)

/** The marine areas each region groups, from the OpenAPI's `MarineRegionCode`. */
const MARINE_REGIONS: Record<string, string[]> = {
  AL: ['PK'],
  AT: ['AM', 'AN'],
  GL: ['LC', 'LE', 'LH', 'LM', 'LO', 'LS', 'SL'],
  GM: ['GM'],
  PA: ['PZ'],
  PI: ['PH', 'PM', 'PS'],
}

/** Each alert's zone and county codes, after checking there is at least one alert. */
function ugcCodes(page: {
  type: string
  features: { properties: { geocode?: { UGC?: string[] } } }[]
}): string[][] {
  expect(page.type).toBe('FeatureCollection')
  expect(page.features.length, 'nothing was in effect there when this was recorded').toBeGreaterThan(0)
  return page.features.map(feature => feature.properties.geocode!.UGC!)
}

const SPGDS = recorded<{ published: string }>('radar/list_spgds/examples/one_minute.request.json')
const QUEUE = recorded<{ host: RadarHost; station: string; arrived: string; limit: number }>(
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

/** The response half of another recorded example, as it came off the wire. */
function payload<T>(file: string): T {
  const full = path.join(projectRoot, 'spec/endpoints', file)
  return (JSON.parse(readFileSync(full, 'utf8')) as { payload: T }).payload
}

const OBSERVATION = recorded<{ station_id: string; time: string }>(
  'stations/get_observation/examples/ksea_metar.request.json',
)
const BRIEFING = recorded<{ office_id: string }>(
  'offices/get_briefing/examples/active.request.json',
)
const HEADLINE = recorded<{ office_id: string; headline_id: string }>(
  'offices/get_headline/examples/wakefield.request.json',
)
const RADIO_PAGE = recorded<{ cursor: string }>(
  'radio/list_transmitters/examples/last_page.request.json',
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

  it('stations.listStations sends two ids as one comma-separated item, and both come back', async () => {
    // The service keeps only the last of a repeated key, so `?id=KSEA&id=KPDX` would answer
    // with KPDX alone. The endpoint declares `match.query_arrays: "comma"`, so the mock 422s
    // any form but `?id=KSEA,KPDX`.
    const asked = recorded<{ id: string[] }>('stations/list_stations/examples/two_ids.request.json')
    expect(asked.id).toHaveLength(2)
    const page = await client.stations.listStations({ id: asked.id })
    const returned = page.features.map(feature => feature.properties.stationIdentifier)
    expect(returned.sort()).toEqual([...asked.id].sort())
  })

  it('stations.listStations sends a list filter as text, not a stringified array', async () => {
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

  it('alerts.listAlerts honours the limit and the window, newest first', async () => {
    const page = await client.alerts.listAlerts({
      start: new Date(ALERT_WINDOW.start),
      end: new Date(ALERT_WINDOW.end),
      status: ALERT_WINDOW.status,
      limit: ALERT_WINDOW.limit,
    })
    expect(page.features.length).toBe(ALERT_WINDOW.limit)
    const sent = page.features.map(feature => feature.properties.sent!.getTime())
    expect([...sent].sort((a, b) => b - a)).toEqual(sent)
    for (const moment of sent) {
      expect(moment).toBeGreaterThanOrEqual(Date.parse(ALERT_WINDOW.start))
      expect(moment).toBeLessThanOrEqual(Date.parse(ALERT_WINDOW.end))
    }
    for (const feature of page.features) expect(feature.properties.status).toBe('Actual')
    expect(page.pagination!.next).toContain('cursor=')
  })

  it('alerts.countActiveAlerts: land and marine add up to the total', async () => {
    const count = await client.alerts.countActiveAlerts({})
    expect(count.total).toBe(count.land + count.marine)
    // The regions need not add up to `marine`: the service has counted one over it.
    for (const n of Object.values(count.regions)) expect(n).toBeGreaterThan(0)
    for (const region of Object.keys(count.regions)) expect(Object.keys(MARINE_REGIONS)).toContain(region)
    expect(Object.keys(count.zones).length).toBeGreaterThan(0)
    expect(Object.keys(count.areas).length).toBeGreaterThan(0)
  })

  it('alerts.getActiveAlertsForZone returns alerts for the zone in the path', async () => {
    // Not every alert names the zone: a county's alerts include ones for the forecast zones
    // overlapping it. Each is held to the zone's state or marine area, one to the zone.
    const zone = ugcCodes(await client.alerts.getActiveAlertsForZone({ zone_id: ZONE.zone_id }))
    expect(zone.some(codes => codes.includes(ZONE.zone_id))).toBe(true)
    for (const codes of zone) expect(codes.some(code => code.startsWith(ZONE.zone_id.slice(0, 2)))).toBe(true)
  })

  it('alerts.getActiveAlertsForArea returns alerts covering the area in the path', async () => {
    for (const codes of ugcCodes(await client.alerts.getActiveAlertsForArea({ area: AREA.area }))) {
      expect(codes.some(code => code.startsWith(AREA.area))).toBe(true)
    }
  })

  it('alerts.getActiveAlertsForRegion returns alerts covering the region in the path', async () => {
    const areas = MARINE_REGIONS[REGION.region]!
    for (const codes of ugcCodes(await client.alerts.getActiveAlertsForRegion({ region: REGION.region }))) {
      expect(codes.some(code => areas.includes(code.slice(0, 2)))).toBe(true)
    }
  })

  it('alerts.listAlertTypes lists each event name once', async () => {
    const types = (await client.alerts.listAlertTypes({})).eventTypes
    expect(types.length).toBeGreaterThan(100)
    expect(new Set(types).size).toBe(types.length)
    for (const name of ['Tornado Warning', 'Severe Thunderstorm Warning', 'Winter Storm Watch']) {
      expect(types).toContain(name)
    }
  })

  it('glossary.listTerms returns the whole glossary in one response', async () => {
    const terms = (await client.glossary.listTerms({})).glossary
    expect(terms.length).toBeGreaterThan(3000)
    expect(terms.some(entry => entry.term === '1-2-3 Rule')).toBe(true)
    for (const entry of terms) {
      expect(entry.term).toBeTruthy()
      expect(entry.definition).toBeTruthy()
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

  it('zones.listZones sends two ids as one comma-separated item, and both come back', async () => {
    const asked = recorded<{ id: string[] }>('zones/list_zones/examples/two_ids.request.json')
    expect(asked.id).toHaveLength(2)
    const page = await client.zones.listZones({ id: asked.id })
    const zones = page.features.map(feature => isZone(feature, false))
    expect(zones.map(zone => zone.id).sort()).toEqual([...asked.id].sort())
    expect(new Set(zones.map(zone => zone.type))).toEqual(new Set(['public', 'county']))
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

  it('products.listProducts honours the type, the limit and a window whose end is exclusive', async () => {
    const page = await client.products.listProducts({
      type: PRODUCTS.type,
      start: new Date(PRODUCTS.start),
      end: new Date(PRODUCTS.end),
      limit: PRODUCTS.limit,
    })
    const products = page['@graph']
    isProductList(products, PRODUCTS.type[0]!)
    expect(products).toHaveLength(PRODUCTS.limit)
    const [start, end] = [Date.parse(PRODUCTS.start), Date.parse(PRODUCTS.end)]
    for (const product of products) {
      expect(product.issuanceTime.getTime()).toBeGreaterThanOrEqual(start)
      expect(product.issuanceTime.getTime()).toBeLessThan(end)
    }
  })

  it('products.listLocations keeps the nulls the service sends for nameless ids', async () => {
    const { locations } = await client.products.listLocations({})
    expect(Object.keys(locations).length).toBeGreaterThan(1000)
    expect(locations.SEW).toBe('Seattle/Tacoma, WA')
    expect(Object.values(locations)).toContain(null)
  })

  it('products.getProduct returns the product the id names, with its text', async () => {
    const product = await client.products.getProduct({ product_id: PRODUCT.product_id })
    expect(product.id).toBe(PRODUCT.product_id)
    expect(product.productCode).toBe('AFD')
    expect(product.issuingOffice).toBe('KSEW')
    expect(product.productText).toContain('AFDSEW')
    expect(product.productText).toContain('Area Forecast Discussion')
  })

  it('products.listProductsByType returns one type from more than one office', async () => {
    const page = await client.products.listProductsByType({ type_id: PRODUCT_TYPE.type_id })
    isProductList(page['@graph'], PRODUCT_TYPE.type_id)
    expect(new Set(page['@graph'].map(product => product.issuingOffice)).size).toBeGreaterThan(1)
  })

  it('products.listLocationsForType names every location that issues the type', async () => {
    const { locations } = await client.products.listLocationsForType({ type_id: 'AFD' })
    expect(Object.keys(locations).length).toBeGreaterThan(100)
    expect(locations.SEW).toBe('Seattle/Tacoma, WA')
    for (const name of Object.values(locations)) expect(name).toBeTruthy()
  })

  it('products.listLocationsForType turns the empty list the service sends into an empty map', async () => {
    // For a type nobody issues the service sends `"locations": []`, not `{}`. The core
    // normalises it (`meta.empty_map`), so validation passes and the type holds.
    const { locations } = await client.products.listLocationsForType({ type_id: 'AGF' })
    expect(Array.isArray(locations)).toBe(false)
    expect(locations).toEqual({})
  })

  it('products.listProducts sends two types as one comma-separated item, and both come back', async () => {
    // `type=AFD&type=ZFP` would answer with ZFP alone; the mock refuses any form but
    // `type=AFD,ZFP` (`match.query_arrays: "comma"`).
    const asked = recorded<{ type: string[]; location: string[]; start: string; end: string; limit: number }>(
      'products/list_products/examples/two_types.request.json',
    )
    expect(asked.type).toHaveLength(2)
    const page = await client.products.listProducts({
      type: asked.type,
      location: asked.location,
      start: new Date(asked.start),
      end: new Date(asked.end),
      limit: asked.limit,
    })
    expect(new Set(page['@graph'].map(product => product.productCode))).toEqual(new Set(asked.type))
  })

  it('products.listTypesForLocation answers in the product-type vocabulary', async () => {
    const types = await client.products.listTypesForLocation({ location_id: 'SEW' })
    const codes = types['@graph'].map(entry => entry.productCode)
    expect(codes).toContain('AFD')
    expect([...new Set(codes)].sort()).toEqual(codes)
    expect(codes.length).toBeGreaterThan(10)
    expect(codes.length).toBeLessThan(300)
  })

  it('products.listProductsByTypeAndLocation returns only that office', async () => {
    const page = await client.products.listProductsByTypeAndLocation({ type_id: 'AFD', location_id: 'SEW' })
    isProductList(page['@graph'], 'AFD', 'KSEW')
  })

  it('products.getLatestProduct returns the newest one, with its text', async () => {
    const product = await client.products.getLatestProduct({ type_id: 'AFD', location_id: 'SEW' })
    expect(product.productCode).toBe('AFD')
    expect(product.issuingOffice).toBe('KSEW')
    expect(product.productText).toContain('AFDSEW')
  })

  it('stations.getStation keeps the whole feature: the geometry is the only place it is', async () => {
    const station = await client.stations.getStation({ station_id: 'KSEA' })
    expect(station.type).toBe('Feature')
    expect(station.id).toBe('https://api.weather.gov/stations/KSEA')
    isPoint(station.geometry)
    const [longitude, latitude] = station.geometry!.coordinates
    expect(Math.round(latitude)).toBe(47)
    expect(Math.round(longitude)).toBe(-122)
    expect(station.properties.stationIdentifier).toBe('KSEA')
    expect(station.properties.timeZone).toBe('America/Los_Angeles')
    isMeasurement(station.properties.elevation!, 'wmoUnit:m')
    expect(station.properties.county!.endsWith('/zones/county/WAC033')).toBe(true)
  })

  it('stations.getObservation returns the observation at exactly the moment asked', async () => {
    const observation = await client.stations.getObservation({
      station_id: OBSERVATION.station_id,
      time: new Date(OBSERVATION.time),
    })
    expect(observation.stationId).toBe(OBSERVATION.station_id)
    expect(observation.timestamp.getTime()).toBe(new Date(OBSERVATION.time).getTime())
    expect(observation.rawMessage!.startsWith(`${OBSERVATION.station_id} `)).toBe(true)
    isMeasurement(observation.temperature, 'wmoUnit:degC')
  })

  it('stations.listTafs answers newest first, its WKT point latitude first', async () => {
    const tafs = await client.stations.listTafs({ station_id: 'KSEA' })
    const graph = tafs['@graph']
    expect(graph.length).toBeGreaterThan(10)
    const issued = graph.map(taf => taf.issueTime.getTime())
    expect([...issued].sort((a, b) => b - a)).toEqual(issued)
    for (const taf of graph) {
      expect(taf.location).toBe('KSEA')
      expect(taf.id.startsWith('https://api.weather.gov/stations/KSEA/tafs/')).toBe(true)
      expect(taf.issueTime.getTime()).toBeLessThanOrEqual(taf.start.getTime())
      expect(taf.start.getTime()).toBeLessThan(taf.end.getTime())
    }
    const [longitude, latitude] = payload<{ geometry: { coordinates: [number, number] } }>(
      'stations/get_station/examples/ksea.response.json',
    ).geometry.coordinates
    const [first, second] = graph[0].geometry!.replace('POINT(', '').replace(')', '').split(' ')
    expect([Number(first), Number(second)]).toEqual([
      Math.round(latitude * 100) / 100,
      Math.round(longitude * 100) / 100,
    ])
  })

  it('offices.getBriefing returns an active briefing and the PDF it points at', async () => {
    const { briefing } = await client.offices.getBriefing({ office_id: BRIEFING.office_id })
    expect(briefing).not.toBeNull()
    expect(briefing!.officeId).toBe(BRIEFING.office_id)
    expect(briefing!.startTime.getTime()).toBeLessThan(briefing!.endTime.getTime())
    expect(briefing!.download).toBe(
      `https://api.weather.gov/offices/${BRIEFING.office_id}/briefing/download/${briefing!.id}`,
    )
  })

  it('offices.getBriefing answers an honest null for an office with none out', async () => {
    const { briefing } = await client.offices.getBriefing({ office_id: 'SEW' })
    expect(briefing).toBeNull()
  })

  it('offices.listHeadlines links each headline, its HTML repeating its title', async () => {
    const headlines = await client.offices.listHeadlines({ office_id: 'AKQ' })
    const graph = headlines['@graph']
    expect(graph.length).toBeGreaterThan(0)
    for (const headline of graph) {
      expect(headline.office).toBe('https://api.weather.gov/offices/AKQ')
      expect(headline['@id']).toBe(`${headline.office}/headlines/${headline.id}`)
      expect(headline.content).toContain(headline.title)
      expect(headline.summary === null || typeof headline.summary === 'string').toBe(true)
    }
  })

  it('offices.getHeadline returns the headline the office lists', async () => {
    const headline = await client.offices.getHeadline(HEADLINE)
    expect(headline.id).toBe(HEADLINE.headline_id)
    const listed = payload<{ '@graph': { id: string; title: string; link: string }[] }>(
      'offices/list_headlines/examples/wakefield.response.json',
    )['@graph'].find(entry => entry.id === headline.id)!
    expect(headline.title).toBe(listed.title)
    expect(headline.link).toBe(listed.link)
  })

  it('offices.listWeatherStories returns each graphic with its text', async () => {
    const { stories } = await client.offices.listWeatherStories({ office_id: 'AKQ' })
    expect(stories.length).toBeGreaterThan(0)
    for (const story of stories) {
      expect(story.officeId).toBe('AKQ')
      expect(story.title && story.description).toBeTruthy()
      expect(story.startTime.getTime()).toBeLessThan(story.endTime.getTime())
      if (story.download !== null) {
        expect(
          story.download.startsWith('https://api.weather.gov/offices/AKQ/weatherstories/download/'),
        ).toBe(true)
      }
    }
  })

  it('radio.listTransmitters on the last page: short, no next page, repeats and all', async () => {
    const page = await client.radio.listTransmitters({ cursor: RADIO_PAGE.cursor })
    const graph = page['@graph']
    expect(graph.length).toBeGreaterThan(0)
    expect(graph.length).toBeLessThan(500)
    expect(page.pagination).toBeUndefined()
    const calls = graph.map(transmitter => transmitter.callSign)
    expect(new Set(calls).size).toBeLessThan(calls.length)
    for (const transmitter of graph) {
      expect(transmitter['@id']).toBe(`https://api.weather.gov/radio/${transmitter.callSign}`)
      expect(transmitter.sameCodes!.length).toBe(transmitter.counties.length)
      expect(Number(transmitter.transmitterFrequency)).toBeGreaterThan(162)
      expect(Number(transmitter.transmitterFrequency)).toBeLessThan(163)
    }
  })

  it('radio.getTransmitter returns the one zones.listTransmitters found for the county', async () => {
    const transmitter = await client.radio.getTransmitter({ call_sign: 'KHB60' })
    expect(transmitter.callSign).toBe('KHB60')
    expect(transmitter['@id']).toBe('https://api.weather.gov/radio/KHB60')
    const county = payload<{
      '@graph': { callSign: string; counties: string[]; transmitterFrequency: string }[]
    }>('zones/list_transmitters/examples/king_county.response.json')['@graph'].find(
      entry => entry.callSign === 'KHB60',
    )!
    expect(transmitter.counties).toEqual(county.counties)
    expect(transmitter.transmitterFrequency).toBe(county.transmitterFrequency)
  })

  it('aviation.getCwsu is an organization, like an office, without its zones', async () => {
    const unit = await client.aviation.getCwsu({ cwsu_id: 'ZSE' })
    expect(unit.id).toBe('ZSE')
    expect(unit.name).toBe('Seattle, WA')
    expect(unit.address?.addressRegion).toBe('WA')
    expect(unit.nwsRegion).toBe('wr')
    expect('responsibleForecastZones' in unit).toBe(false)
  })

  it('aviation.listCwas answers the week newest first, each named by date and sequence', async () => {
    const page = await client.aviation.listCwas({ cwsu_id: 'ZFW' })
    expect(page.features.length).toBeGreaterThan(0)
    isNewestFirst(page.features)
    for (const feature of page.features) {
      const advisory = feature.properties
      expect(advisory.cwsu).toBe('ZFW')
      expect(advisory.sequence).toBeGreaterThanOrEqual(101)
      expect(advisory.start.getTime()).toBeLessThanOrEqual(advisory.end.getTime())
      const suffix = `/cwsus/ZFW/cwas/${utcDay(advisory.issueTime)}/${advisory.sequence}`
      expect(advisory.id.endsWith(suffix)).toBe(true)
      if (feature.geometry !== null) isAdvisoryArea(feature.geometry, FORT_WORTH)
    }
  })

  it('aviation.getCwa returns the advisory the list holds, area included', async () => {
    const feature = await client.aviation.getCwa({ ...CWA, date: DateIso.of(CWA.date) })
    const advisory = feature.properties
    expect([advisory.cwsu, advisory.sequence]).toEqual([CWA.cwsu_id, CWA.sequence])
    expect(utcDay(advisory.issueTime)).toBe(CWA.date)
    expect(advisory.text).toBeTruthy()
    isAdvisoryArea(feature.geometry, FORT_WORTH)
    // The list keeps a week. The service answers 500 for most single advisories (see the
    // endpoint's notes), so a re-recording can renew the list and keep an older advisory
    // here; one from inside the list's week must be in it.
    const listed = 'aviation/list_cwas/examples/fort_worth.response.json'
    const full = path.join(projectRoot, 'spec/endpoints', listed)
    const issued = (JSON.parse(readFileSync(full, 'utf8')) as {
      payload: { features: { properties: { issueTime: string } }[] }
    }).payload.features.map(feature => Date.parse(feature.properties.issueTime))
    if (advisory.issueTime.getTime() >= Math.min(...issued)) {
      expect(recordedIds(listed)).toContain(advisory.id)
    }
  })

  it('aviation.listSigmets by sequence alone reaches back through the week', async () => {
    const page = await client.aviation.listSigmets({ sequence: '1E' })
    expect(page.features.length).toBeGreaterThan(0)
    isNewestFirst(page.features)
    expect(new Set(page.features.map(f => f.properties.sequence))).toEqual(new Set(['1E']))
    expect(new Set(page.features.map(f => utcDay(f.properties.issueTime))).size).toBeGreaterThan(1)
    for (const feature of page.features) {
      expect(feature.properties.atsu).toBe('KKCI')
      if (feature.geometry !== null) isAdvisoryArea(feature.geometry, EAST)
    }
  })

  it('aviation.listSigmetsForAtsu answers one unit, newest first, over several days', async () => {
    const page = await client.aviation.listSigmetsForAtsu({ atsu: 'ANC' })
    expect(page.features.length).toBeGreaterThan(0)
    isNewestFirst(page.features)
    for (const feature of page.features) isSigmetOf(feature, 'ANC')
    expect(new Set(page.features.map(f => utcDay(f.properties.issueTime))).size).toBeGreaterThan(1)
  })

  it('aviation.listSigmetsForAtsuOnDate answers that day only, all in the week', async () => {
    const page = await client.aviation.listSigmetsForAtsuOnDate({
      atsu: SIGMETS_ON_DATE.atsu,
      date: DateIso.of(SIGMETS_ON_DATE.date),
    })
    expect(page.features.length).toBeGreaterThan(0)
    isNewestFirst(page.features)
    const week = recordedIds('aviation/list_sigmets_for_atsu/examples/anchorage.response.json')
    for (const feature of page.features) {
      const sigmet = isSigmetOf(feature, SIGMETS_ON_DATE.atsu)
      expect(utcDay(sigmet.issueTime)).toBe(SIGMETS_ON_DATE.date)
      expect(week).toContain(sigmet.id)
    }
  })

  it('aviation.getSigmet returns the message the unit, date and minute name', async () => {
    const feature = await client.aviation.getSigmet({ ...SIGMET, date: DateIso.of(SIGMET.date) })
    const sigmet = isSigmetOf(feature, SIGMET.atsu)
    expect([utcDay(sigmet.issueTime), utcMinute(sigmet.issueTime)]).toEqual([SIGMET.date, SIGMET.time])
    expect(feature.geometry).not.toBeNull()
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

  it('radar.listStations sends two kinds as one comma-separated item, and both come back', async () => {
    // The service keeps only the last of a repeated key, so `?stationType=TDWR&stationType=Profiler`
    // would answer with the profilers alone. The endpoint declares `match.query_arrays: "comma"`,
    // so the mock 422s any form but `?stationType=TDWR,Profiler`.
    const asked = recorded<{ stationType: string[] }>('radar/list_stations/examples/tdwr_and_profilers.request.json')
    expect(asked.stationType).toHaveLength(2)
    const page = await client.radar.listStations({ stationType: asked.stationType })
    const kinds = new Set(page.features.map(feature => feature.properties.stationType))
    expect(kinds).toEqual(new Set(asked.stationType))
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
