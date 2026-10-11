# TRU-1043 Python review reproductions (weather-gov #13, #15, #18, #19, #20)

- `pr19_test_proxy_repr.py`: `repr(Weather.new(proxy='http://user:S3CRET@...'))` prints the password.
  Fails on #19 (7f08602); passes with `field(default_factory=HttpClient, repr=False)` on `Transport.http`.
  Run: copy into a #19 checkout and `.venv/bin/python -m pytest pr19_test_proxy_repr.py -q`.
- `post15_list_filter_conflict.sh`: main + #15 + #13 and main + #15 + #18 each fail 2 tests in `test_spec.py`.
- `pr13_locations_for_type_live.py`: live, `products.list_locations_for_type` raises `ValidationError()` on 26 of the first 60 type codes (`"locations": []`).
- `pr18_radar_live_sweep.py`: live, the radar group validates over 208 stations, all servers, spgds and both queues (clean).
- `pr15_query_form.py`: the URL #15's core builds for list filters (`id=KSEA%2CKPDX`, empty list dropped).
