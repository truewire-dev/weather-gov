/** Offline mutations of a recording; these are not live evidence. */
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, it } from 'vitest'
import { Alert } from '../src/weather-gov/types/index.js'
import { projectRoot } from './setup.js'

function alert(): Record<string, unknown> {
  return JSON.parse(readFileSync(path.join(projectRoot,
    'spec/endpoints/alerts/list_alerts/examples/first_page.response.json'), 'utf8'))
    .payload.features[0].properties
}

it.each(['description', 'response'] as const)('preserves explicit null in %s', field => {
  const body = alert()
  body[field] = null
  expect(Alert.parse(body)[field]).toBeNull()
})

it('keeps non-null values, optional response, and required description', () => {
  const body = { ...alert(), description: 'Take shelter.', response: 'Shelter' } as Record<string, unknown>
  expect(Alert.parse(body)).toMatchObject({ description: 'Take shelter.', response: 'Shelter' })
  delete body.response
  expect(Alert.parse(body)).not.toHaveProperty('response')
  delete body.description
  expect(() => Alert.parse(body)).toThrow()
})

it.each([
  ['description', 42], ['description', {}], ['response', 'shelter'], ['response', 42],
])('rejects invalid %s: %j', (field, value) => {
  const body = alert()
  body[String(field)] = value
  expect(() => Alert.parse(body)).toThrow()
})
