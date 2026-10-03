"""Consumer checks for client bbacd505 and the published Python core 0.2.1.

Run from the repository root with the merged toolchain on PYTHONPATH:
  .venv/bin/python dev/review/TRU-994/consumer.py
  .venv/bin/pyright --pythonpath .venv/bin/python dev/review/TRU-994/consumer.py
"""

import asyncio
import json
from pathlib import Path
from typing import Any, assert_type

from pydantic import ValidationError as PydanticValidationError
from truewire.mock import running_mock_servers
from truewire_core.exceptions import ValidationError
from truewire_core.validation import validator
from weather_gov import Weather
from weather_gov.schemas import (
    AlertFeature,
    AlertGeometry,
    OfficeHeadline,
    PointGeometry,
    Position,
    TransmitterCollection,
    ZoneFeature,
    ZoneGeometry,
    ZoneKind,
)

ROOT = Path(__file__).resolve().parents[3]


def payload(endpoint: str, name: str) -> Any:
    path = ROOT / "spec/endpoints" / endpoint / "examples" / f"{name}.response.json"
    return json.loads(path.read_text())["payload"]


def shared_types() -> None:
    point: PointGeometry = {"type": "Point", "coordinates": (-122.31361, 47.44472)}
    assert_type(point["coordinates"], Position)
    assert validator(PointGeometry).python(point) == point

    zone = validator(ZoneFeature).python(payload("zones/get_zone", "seattle"))
    assert_type(zone["properties"]["type"], ZoneKind)
    assert_type(zone["geometry"], ZoneGeometry)
    assert zone["geometry"] is not None
    assert zone["geometry"]["type"] == "Polygon"
    assert isinstance(zone["geometry"]["coordinates"][0][0], tuple)
    assert zone["properties"]["@id"].endswith(zone["properties"]["id"])
    nullable_zone = dict(payload("zones/get_zone", "seattle"), geometry=None)
    assert validator(ZoneFeature).python(nullable_zone)["geometry"] is None
    del nullable_zone["geometry"]
    try:
        validator(ZoneFeature).python(nullable_zone)
    except ValidationError as error:
        cause = error.__cause__
        assert isinstance(cause, PydanticValidationError)
        assert any(
            e["loc"] == ("geometry",) and e["type"] == "missing" for e in cause.errors()
        )
    else:
        raise AssertionError("ZoneFeature accepted a missing required geometry")

    alert = payload("alerts/get_alert", "one")
    parsed_alert = validator(AlertFeature).python(alert)
    assert "geometry" in parsed_alert
    assert_type(parsed_alert["geometry"], AlertGeometry)
    assert parsed_alert["geometry"] is not None
    alert["geometry"] = None
    null_alert = validator(AlertFeature).python(alert)
    assert "geometry" in null_alert and null_alert["geometry"] is None
    del alert["geometry"]
    assert "geometry" not in validator(AlertFeature).python(alert)


async def calls() -> None:
    with running_mock_servers(ROOT) as mock:
        async with Weather.new(
            contact="review@truewire.dev", base_url=mock.http_base_url
        ) as weather:
            headlines = await weather.offices.list_headlines(office_id="AKQ")
            target = payload("offices/get_headline", "wakefield")["id"]
            listed = next(h for h in headlines["@graph"] if h["id"] == target)
            headline = await weather.offices.get_headline(
                office_id="AKQ", headline_id=listed["id"]
            )
            assert_type(headline, OfficeHeadline)
            assert headline["id"] == target
            assert headline["@id"] != headline["id"]
            assert headline["title"] == listed["title"]

            request_path = (
                ROOT
                / "spec/endpoints/radio/list_transmitters/examples/last_page.request.json"
            )
            cursor = json.loads(request_path.read_text())["request"]["cursor"]
            radio = await weather.radio.list_transmitters(cursor)
            assert_type(radio, TransmitterCollection)
            assert radio["@graph"]
            raw = await weather.radio.list_transmitters(cursor, validate=False)
            assert_type(raw, Any)
            assert raw == payload("radio/list_transmitters", "last_page")


if __name__ == "__main__":
    shared_types()
    asyncio.run(calls())
    print(
        "PASS: shared aliases, geometry missing/null/value, headline lookup, radio typed/raw calls"
    )
