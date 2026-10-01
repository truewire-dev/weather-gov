# TRU-603: Python review reproductions for PR #17 at afe2e7c

Run from the repository root, with `packages/python[dev]` installed over typed `truewire` at
`c1d4c279` (truewire 0.11.0, truewire-core 0.3.0).

- `python review/TRU-603/date_utc.py`: exits 1 while a `datetime` passed as a documented
  UTC `date` is sent as its local calendar day; exits 0 once the request is validated (or
  normalised to UTC) before it is rendered.
- `python review/TRU-603/user.py`: prints every URL the aviation methods build, against the
  recorded responses through an `httpx.MockTransport`.
- `typing_aviation.py`: copy into `packages/python/test/` and run
  `pyright --project packages/python/pyrightconfig.json <file>`. Expected: four errors, at
  lines 17 (`email` NotRequired), 33 (`'ZZZ'` not a `CwsuId`), 34 (`str` date) and 40
  (`get_sigmet` takes no positional `atsu`); nothing else.
- `typing_raw.py`: copy into `packages/python/test/` and run pyright the same way. Expected: 0
  errors. Python's `validate=False` overload takes an omitted or `None` request and gives
  `Any`, so the TypeScript optional-request overload defect (TRU-604) does not occur here.
