import { expectTypeOf } from 'vitest'
import type { Offices } from '../src/weather-gov/offices/index.js'
import type { ActiveBriefing, GetBriefing } from '../src/weather-gov/offices/get_briefing.js'

declare const endpoint: GetBriefing
declare const router: Offices
const request = { office_id: 'AKQ' }

// Promoted from the widened-options consumer regression in TRU-995. truewire 0.11 still
// types widened (`{ validate: boolean }`) options as validated; the widened and dynamic
// cases return after the next release (TRU-1007, TRU-1046).
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

void rawLiterals
void validatedControls
