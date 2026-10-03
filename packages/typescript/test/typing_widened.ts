import { expectTypeOf } from 'vitest'
import type { Offices } from '../src/weather-gov/offices/index.js'
import type { ActiveBriefing, GetBriefing } from '../src/weather-gov/offices/get_briefing.js'

declare const endpoint: GetBriefing
declare const router: Offices
declare const validate: boolean
const request = { office_id: 'AKQ' }
const options: NonNullable<Parameters<Offices['getBriefing']>[1]> = { validate: false }

// Promoted from the widened-options consumer regression in TRU-995.
async function widenedOptions() {
  const fromEndpoint = await endpoint.getBriefing(request, options)
  const fromRouter = await router.getBriefing(request, options)
  expectTypeOf(fromEndpoint).toEqualTypeOf<unknown>()
  expectTypeOf(fromRouter).toEqualTypeOf<unknown>()
  // @ts-expect-error Widened validation options can return raw JSON and must be unknown.
  fromEndpoint.briefing!.startTime.getTime()
  // @ts-expect-error Routers must preserve the same guarantee as endpoint classes.
  fromRouter.briefing!.startTime.getTime()
}

async function dynamicOptions() {
  const fromEndpoint = await endpoint.getBriefing(request, { validate })
  const fromRouter = await router.getBriefing(request, { validate })
  expectTypeOf(fromEndpoint).toEqualTypeOf<unknown>()
  expectTypeOf(fromRouter).toEqualTypeOf<unknown>()
  // @ts-expect-error A runtime boolean cannot guarantee validated timestamps.
  fromEndpoint.briefing!.startTime.getTime()
  // @ts-expect-error A router cannot guarantee validation for a runtime boolean either.
  fromRouter.briefing!.startTime.getTime()
}

async function rawLiterals() {
  const fromEndpoint = await endpoint.getBriefing(request, { validate: false })
  const fromRouter = await router.getBriefing(request, { validate: false })
  expectTypeOf(fromEndpoint).toEqualTypeOf<unknown>()
  expectTypeOf(fromRouter).toEqualTypeOf<unknown>()
  // @ts-expect-error Literal false must continue to return unknown.
  fromEndpoint.briefing!.startTime.getTime()
  // @ts-expect-error The router's literal-false overload must also return unknown.
  fromRouter.briefing!.startTime.getTime()
}

async function validatedControls() {
  const explicitEndpoint = await endpoint.getBriefing(request, { validate: true })
  const explicitRouter = await router.getBriefing(request, { validate: true })
  const defaultEndpoint = await endpoint.getBriefing(request)
  const defaultRouter = await router.getBriefing(request)
  expectTypeOf(explicitEndpoint).toEqualTypeOf<ActiveBriefing>()
  expectTypeOf(explicitRouter).toEqualTypeOf<ActiveBriefing>()
  expectTypeOf(defaultEndpoint).toEqualTypeOf<ActiveBriefing>()
  expectTypeOf(defaultRouter).toEqualTypeOf<ActiveBriefing>()
  explicitEndpoint.briefing!.startTime.getTime()
  explicitRouter.briefing!.startTime.getTime()
  defaultEndpoint.briefing!.startTime.getTime()
  defaultRouter.briefing!.startTime.getTime()
}

void widenedOptions
void dynamicOptions
void rawLiterals
void validatedControls
