/**
 * The weather.gov HTTP transport: the `User-Agent` the service asks for, the envelope, and
 * the RFC 7807 error mapping.
 *
 * Nothing here is generated, and regenerating the client never touches it. Every generated
 * endpoint is constructed with this transport and calls `request(...)` on it; the interface
 * is structural (`HttpEndpoint<DefaultMeta>`), so this satisfies the generated client by
 * shape rather than by inheritance.
 */
import {
  ApiError, BadRequest, HttpClient, RateLimited,
  type HttpCall, type HttpEndpoint,
} from '@truewire/core'
import type { DefaultMeta } from '../meta.js'

/**
 * The one host. There is no staging environment and no versioned prefix: the API is
 * versioned through the `Accept` header instead.
 */
export const API = 'https://api.weather.gov'

/**
 * What most of this API answers in. The service also serves `application/ld+json` and
 * `application/vnd.noaa.dwml+xml` from the same paths, so asking matters -- and asking for
 * `application/geo+json` is what pins the response shapes these codecs describe.
 */
export const GEO_JSON = 'application/geo+json'

/**
 * The `User-Agent` the service asks for: who is calling, and how to reach them.
 *
 * The published guidance is a string identifying the application with contact information,
 * and a caller that sends nothing useful can be blocked. So `contact` is required rather
 * than optional with a default that would be a lie.
 */
export function userAgent(contact: string): string {
  return `truewire-weather-gov (${contact})`
}

/**
 * Map a non-2xx answer onto the runtime's errors.
 *
 * The service answers errors in RFC 7807 problem detail, and a bad parameter adds a
 * `parameterErrors` list naming exactly which one and why. That list is the most useful
 * thing in the body, so it is what the message leads with when it is there.
 */
export function raiseForStatus(method: string, path: string, status: number, text: string): never {
  let reason = text.slice(0, 300)
  let body: unknown
  try {
    body = JSON.parse(text)
  } catch {
    body = undefined
  }
  if (body !== null && typeof body === 'object') {
    const { parameterErrors, detail, title } = body as {
      parameterErrors?: unknown
      detail?: unknown
      title?: unknown
    }
    if (Array.isArray(parameterErrors) && parameterErrors.length > 0) {
      reason = parameterErrors
        .map(item => {
          const { parameter, message } = item as { parameter?: unknown; message?: unknown }
          return `${String(parameter)}: ${String(message)}`
        })
        .join('; ')
    } else if (typeof detail === 'string') reason = detail
    else if (typeof title === 'string') reason = title
  }
  const message = `${method} ${path}: HTTP ${status}: ${reason}`
  if (status === 400) throw new BadRequest(message)
  if (status === 429) throw new RateLimited(message)
  throw new ApiError(message)
}

/**
 * Read the declared envelope payload off a decoded response body.
 *
 * `payload` is the dotted path an endpoint declared, `undefined` for one that declares no
 * envelope. An endpoint that declares one and does not get it is a wire change, not a
 * missing optional field, so it throws rather than handing `undefined` to a codec to
 * report as a type error a frame later.
 */
export function unwrap(raw: unknown, payload: string | undefined): unknown {
  if (payload === undefined) return raw
  let value = raw
  for (const key of payload.split('.')) {
    if (value === null || typeof value !== 'object' || !(key in value)) {
      throw new ApiError(`response has no \`${payload}\` to unwrap; the wire shape has changed`)
    }
    value = (value as Record<string, unknown>)[key]
  }
  return value
}

export interface TransportOptions {
  /**
   * How the service can reach you -- an email address or a project URL. It is sent in
   * `User-Agent` on every call, which the service asks of every caller. There is no API
   * key: this is the whole of identifying yourself.
   */
  contact: string
  /** The host to call. The live API by default; a `truewire mock` address in tests. */
  baseUrl?: string
  /** Validate responses by default; a call's own `validate` option overrides it. */
  validate?: boolean
  /** The `fetch` wrapper to send through; one is made when omitted. */
  http?: HttpClient
}

/** The transport every endpoint group calls: `HttpEndpoint<DefaultMeta>` by shape. */
export class Transport implements HttpEndpoint<DefaultMeta> {
  readonly baseUrl: string
  readonly contact: string
  readonly validate: boolean
  readonly http: HttpClient

  constructor(options: TransportOptions) {
    this.baseUrl = (options.baseUrl ?? API).replace(/\/+$/, '')
    this.contact = options.contact
    this.validate = options.validate ?? true
    this.http = options.http ?? new HttpClient()
  }

  /**
   * Send one call, unwrap the declared envelope, and validate what is left.
   *
   * The order matters: the envelope is read off the decoded body first, and the response
   * codec describes the unwrapped value, not the wire frame the spec's response schema
   * describes.
   */
  async request<Req, Res>(call: HttpCall<Req, Res, DefaultMeta>): Promise<Res> {
    const values =
      call.request !== undefined && call.requestCodec !== undefined
        ? (call.requestCodec.dump(call.request) as Record<string, unknown>)
        : {}
    const method = call.method ?? 'GET'
    const { path, query } = fill(call.path, values)
    const response = await this.http.request(method, this.baseUrl + path, {
      query,
      headers: { Accept: GEO_JSON, 'User-Agent': userAgent(this.contact) },
      signal: call.signal,
    })
    const text = await response.text()
    if (response.status >= 400) raiseForStatus(method, path, response.status, text)
    if (call.responseCodec === undefined) return undefined as Res
    const body: unknown = text === '' ? undefined : JSON.parse(text)
    const value = unwrap(body, call.meta.payload)
    return (call.validate ?? this.validate) ? call.responseCodec.parse(value) : (value as Res)
  }
}

/**
 * The path with its `{name}` placeholders filled, and the rest as query parameters.
 *
 * Two details this API forces:
 *
 * - A list-valued filter (`state`, `severity`) travels as repeated keys, which is what the
 *   service reads and what `truewire mock` matches.
 * - A path value is percent-encoded, with `:` left alone. It is a legal path character
 *   (RFC 3986 `pchar`), an alert id is `urn:oid:...`, and the service publishes that id
 *   inside the URL it hands back -- so encoding it would send a URL the API never printed.
 *   Everything else is encoded, `/` included: no path parameter here is a path fragment,
 *   so a `/` in one would be an injected path segment.
 */
function fill(
  template: string,
  values: Record<string, unknown>,
): { path: string; query: URLSearchParams } {
  let path = template
  const query = new URLSearchParams()
  for (const [name, value] of Object.entries(values)) {
    if (value === null || value === undefined) continue
    if (path.includes(`{${name}}`)) {
      path = path.replace(`{${name}}`, encodePathValue(String(value)))
      continue
    }
    for (const item of Array.isArray(value) ? value : [value]) {
      query.append(name, typeof item === 'object' ? JSON.stringify(item) : String(item))
    }
  }
  return { path, query }
}

/** `encodeURIComponent`, but keeping the `:` that an alert identifier is built from. */
function encodePathValue(value: string): string {
  return encodeURIComponent(value).replaceAll('%3A', ':')
}
