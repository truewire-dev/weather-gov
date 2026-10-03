import type { Offices } from '../../packages/typescript/src/weather-gov/offices/index.js'
import type { GetBriefing } from '../../packages/typescript/src/weather-gov/offices/get_briefing.js'

declare const endpoint: GetBriefing
declare const router: Offices
const options: NonNullable<Parameters<Offices['getBriefing']>[1]> = { validate: false }

async function check() {
  const fromEndpoint = await endpoint.getBriefing({ office_id: 'AKQ' }, options)
  const fromRouter = await router.getBriefing({ office_id: 'AKQ' }, options)
  // @ts-expect-error Widened validation options can return raw JSON and must be unknown.
  fromEndpoint.briefing!.startTime.getTime()
  // @ts-expect-error Routers must preserve the same guarantee as endpoint classes.
  fromRouter.briefing!.startTime.getTime()
}
void check
