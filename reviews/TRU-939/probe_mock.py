"""Run with the isolated 0.11.0 Python; no live API calls or Rust build."""
import json
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import urlopen

from truewire.mock import _query_matches_form

root = Path(sys.argv[1]).resolve()
cli = Path(sys.executable).with_name("truewire")
mock = subprocess.Popen(
    [str(cli), "mock", "--project", str(root), "--http-port", "0", "--ws-port", "0"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
)
try:
    for line in mock.stdout:
        if line.startswith("HTTP "):
            base = line.split()[1]
            break
    else:
        raise RuntimeError(mock.stderr.read())
    for route, ids, key in [
        ("stations", ["KSEA", "KPDX"], "stationIdentifier"),
        ("zones", ["WAZ315", "WAC033"], "id"),
    ]:
        with urlopen(f"{base}/{route}?id={','.join(ids)}", timeout=10) as response:
            body = json.load(response)
            assert sorted(f["properties"][key] for f in body["features"]) == sorted(ids)
        print(f"PASS {route}: comma returns both requested IDs")
        for query in [f"id={ids[0]}&id={ids[1]}", f"id={','.join(ids)}&id={ids[1]}"]:
            try:
                urlopen(f"{base}/{route}?{query}", timeout=10)
            except HTTPError as error:
                body = json.load(error)
                assert error.code == 422 and body["error"] == "unexpected_parameters", (query, error.code, body)
            else:
                raise AssertionError(f"Repeated key falsely matched: {query}")
            print(f"PASS {route}: rejects {query}")
    cases = [
        ([], {"id": []}, True),
        ([("id", "")], {"id": []}, False),
        ([("flag", "true,false")], {"flag": [True, False]}, True),
        ([("flag", "true"), ("flag", "false")], {"flag": [True, False]}, False),
        ([("flag", "false"), ("limit", "2"), ("point", "47.6,-122.3")],
         {"flag": False, "limit": 2, "point": "47.6,-122.3"}, True),
    ]
    for actual, expected, matches in cases:
        assert _query_matches_form(actual, expected, "comma") is matches
    print("PASS 5 matcher edge cases: empty arrays, boolean arrays/scalars, numbers, scalar commas")
finally:
    mock.terminate()
    try:
        mock.wait(timeout=10)
    except subprocess.TimeoutExpired:
        mock.kill()
        mock.wait()
