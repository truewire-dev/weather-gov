/**
 * The client a caller actually constructs: the generated `Weather` plus the one thing a
 * generated class cannot carry -- a factory that knows the default host and requires the
 * contact the service asks for.
 *
 * Generated TypeScript imports nothing from this package -- it names the contract
 * interfaces and receives an object -- so the factory arrives by subclassing it here rather
 * than by it extending something of ours. Python declares a base in `truewire.toml`
 * instead; either way a caller writes `Weather.new(...)`.
 *
 * There is no `AsyncDisposable` here and no `await using`, unlike the Bluesky showcase.
 * That client holds WebSocket connections and has to close them; this one is `fetch` and a
 * base URL, and owns nothing a caller has to give back.
 */
import { Weather as Generated } from '../main.js'
import { Transport, type TransportOptions } from './http.js'

export type WeatherOptions = TransportOptions

/**
 * The United States National Weather Service API.
 *
 * ```ts
 * const client = Weather.new({ contact: 'you@example.com' })
 * const point = await client.points.getPoint({ latitude: 47.6062, longitude: -122.3321 })
 * const forecast = await client.forecast.getForecast({
 *   office: point.gridId,
 *   grid_x: point.gridX,
 *   grid_y: point.gridY,
 * })
 * ```
 */
export class Weather extends Generated {
  declare readonly core: Transport

  /**
   * Build a client.
   *
   * `contact` is required and has no default: the service asks every caller to identify
   * itself in `User-Agent`, and a default would be a lie about who is calling.
   */
  static new(options: WeatherOptions): Weather {
    return new Weather(new Transport(options))
  }
}
