"""The response annotation is distinct from the endpoint group."""

from weather_gov import Weather
from weather_gov.glossary import Glossary
from weather_gov.glossary.list_terms import GlossaryResponse


async def terms(client: Weather) -> list[str]:
  group: Glossary = client.glossary
  result: GlossaryResponse = await group.list_terms()
  return [entry['term'] for entry in result['glossary']]
