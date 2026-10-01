from typing_extensions import Any, assert_type
from weather_gov import Weather
from weather_gov.schemas import SigmetCollection


async def raw() -> None:
  aviation = Weather.new(contact='review@truewire.dev').aviation
  assert_type(await aviation.list_sigmets(validate=False), Any)
  assert_type(await aviation.list_sigmets(None, validate=False), Any)
  assert_type(await aviation.list_sigmets(None, date=None, sequence=None, validate=False), Any)
  assert_type(await aviation.list_sigmets(), SigmetCollection)
  assert_type(await aviation.get_sigmet(atsu='ANC', date=__import__('datetime').date(2026, 9, 30), time='2005', validate=False), Any)
