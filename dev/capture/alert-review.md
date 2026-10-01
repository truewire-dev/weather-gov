# Nullable alert and cursor recordings

Captured through the generated Python client and `truewire capture` on 2026-10-01.
No authentication is required; use `--new contact=hello@truewire.dev`.

- `alerts.get_alert/null_description`: found by calling `alerts.list_alerts`
  with `limit=500`; two of the newest 500 alerts had an explicit null description.
  Captured the first identifier through `alerts.get_alert`.
- `alerts.get_alert/null_response`: found by calling `alerts.list_alerts` with
  `event=['Civil Emergency Message']` and `limit=500`, then capturing an identifier
  whose response field was explicitly null through `alerts.get_alert`.
- `alerts.list_alerts/second_page`: parsed the `first_page.response.json`
  `payload.pagination.next` URL using `urllib.parse.urlsplit` and `parse_qs`,
  extracted the decoded cursor and added it to the unchanged `first_page` request.
  Three distinct alerts followed the original three, inside the same window and
  with the original `status=['actual']` and `limit=3`.

The exact requests are committed beside their responses. Reproduce any pair by
passing its `request` object to `truewire capture <function> --id <example>` with
`--request` and the contact above. Alert retention is about seven days: an old
identifier or cursor may expire, and reproducing these particular IDs later is
not guaranteed. The null and second-page content assertions in
`packages/python/test/test_recordings.py` must pass before accepting a recapture.

The short-page continuation behavior (100, 76, empty) was observed in the Python
review; this run captured two pages of three. The documented loop's offline test
reproduces 100, 76, empty, and checks the actual outgoing filter and cursor
parameters. Its synthesized pages are test inputs, not verified recordings.
