"""Pyright probe: the aviation surface as a user types it. Expected errors are marked."""
from datetime import date, datetime
from typing_extensions import assert_type

from weather_gov import Weather
from weather_gov.schemas import (
  AdvisoryPolygon, AdvisoryPosition, CenterWeatherAdvisoryCollection, CenterWeatherAdvisoryFeature,
  CwsuId, SigmetCollection, SigmetFeature,
)


async def usage() -> None:
  async with Weather.new(contact='review@truewire.dev') as weather:
    aviation = weather.aviation
    unit = await aviation.get_cwsu('ZSE')
    print(unit['name'], unit['id'])
    print(unit['email'])  # 1: present on all 22 units live, typed NotRequired
    cwas = await aviation.list_cwas('ZFW')
    assert_type(cwas, CenterWeatherAdvisoryCollection)
    for feature in cwas['features']:
      advisory = feature['properties']
      assert_type(advisory['issueTime'], datetime)
      unit_id: CwsuId = advisory['cwsu']
      geometry = feature['geometry']
      if geometry is not None:
        assert_type(geometry, AdvisoryPolygon)
        for lat, lon in geometry['coordinates'][0]:
          print(lat + 0.0, lon + 0.0)
        corner: AdvisoryPosition = geometry['coordinates'][0][0]
        print(corner, unit_id)
    cwa = await aviation.get_cwa('ZFW', date=date(2026, 9, 30), sequence=301)
    assert_type(cwa, CenterWeatherAdvisoryFeature)
    await aviation.get_cwa('ZZZ', date=date(2026, 9, 30), sequence=301)  # 2: expected error, enum
    await aviation.get_cwa('ZFW', date='2026-09-30', sequence=301)  # 3: str date
    sigmets = await aviation.list_sigmets(sequence='1E')
    assert_type(sigmets, SigmetCollection)
    await aviation.list_sigmets(datetime(2026, 9, 30))  # 4: positional `start`
    one = await aviation.get_sigmet(atsu='ANC', date=date(2026, 9, 30), time='2005')
    assert_type(one, SigmetFeature)
    await aviation.get_sigmet('ANC', date=date(2026, 9, 30), time='2005')  # 5: atsu positional?
    await aviation.list_sigmets_for_atsu_on_date('ANC', date=date(2026, 9, 30))
