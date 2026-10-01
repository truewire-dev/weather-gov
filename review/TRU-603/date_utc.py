"""A `date` parameter documented as a UTC date takes an aware datetime, and sends its local day.

truewire_core's DateConverter.parse refuses a non-midnight datetime, but the weather-gov core
renders requests through `validator(...).dump` alone, so that guard never runs on a request.
Exit 1 while the defect stands.
"""
from datetime import datetime, timedelta, timezone
from truewire_core.validation import validator
from weather_gov.core import render
from weather_gov.aviation.list_sigmets_for_atsu_on_date import Request

evening_in_phoenix = datetime(2026, 9, 30, 20, 0, tzinfo=timezone(timedelta(hours=-7)))  # 03:00Z, 1 Oct
sent = render(Request(atsu='ANC', date=evening_in_phoenix), Request)['date']
print('sent date =', sent, '| UTC date =', evening_in_phoenix.astimezone(timezone.utc).date())
try:
  validator(Request).python({'atsu': 'ANC', 'date': evening_in_phoenix})
  print('validator accepts it too')
except Exception as e:
  print('validator refuses it:', type(e).__name__)
raise SystemExit(0 if sent == '2026-10-01' else 1)
