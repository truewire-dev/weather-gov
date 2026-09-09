/**
 * The package's entry point: the hand-written half in front, the generated half behind it.
 *
 * A caller imports `Weather` from here and gets the subclass with the factory on it; the
 * generated types, codecs and `meta` are re-exported unchanged, so the whole surface is one
 * import. Nothing here is generated, and regenerating never touches it.
 */
export { Weather, type WeatherOptions } from './client.js'
export { API, GEO_JSON, raiseForStatus, Transport, unwrap, userAgent, type TransportOptions } from './http.js'

export * from '../types/index.js'
export * from '../meta.js'
export type { CallOptions } from '@truewire/core'
