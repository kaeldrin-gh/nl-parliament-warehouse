"""Feed changes and OData rows for the same version become the same landing row."""

import json
from pathlib import Path

import pytest

from ingest.entities import BY_NAME
from ingest.records import from_feed, from_odata, timestamp
from ingest.syncfeed import Change, parse_page

PARITY = Path(__file__).parent / "fixtures" / "parity"
LOAD_METADATA = {"resume_token", "origin", "batch_id", "loaded_at", "api_updated"}


def _without_load_metadata(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in LOAD_METADATA}


@pytest.mark.parametrize("name", ["Besluit", "Activiteit"])
def test_feed_and_odata_give_the_same_row(name):
    entity = BY_NAME[name]
    (change,) = parse_page((PARITY / f"{name.lower()}_feed.xml").read_bytes()).changes
    item = json.loads((PARITY / f"{name.lower()}_odata.json").read_text(encoding="utf-8"))

    from_the_feed = from_feed(entity, change, "b", "t")
    from_odata_api = from_odata(entity, item, "b", "t")

    assert _without_load_metadata(from_the_feed) == _without_load_metadata(from_odata_api)
    assert from_the_feed["origin"] == "feed" and from_odata_api["origin"] == "snapshot"
    assert from_odata_api["resume_token"] is None


def test_a_decision_keeps_its_case_links():
    (change,) = parse_page((PARITY / "besluit_feed.xml").read_bytes()).changes

    row = from_feed(BY_NAME["Besluit"], change, "b", "t")

    assert row["zaak_ids"] and all(isinstance(z, str) for z in row["zaak_ids"])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-06-24T14:00:00", "2026-06-24T12:00:00Z"),  # summer: UTC+2
        ("2026-01-10T14:00:00", "2026-01-10T13:00:00Z"),  # winter: UTC+1
        ("2026-09-21T17:41:57.1870000", "2026-09-21T15:41:57.187000Z"),  # 7 digits
        ("2026-09-21T17:41:57.187+02:00", "2026-09-21T15:41:57.187000Z"),
        ("2026-09-25T07:44:23.9574701Z", "2026-09-25T07:44:23.957470Z"),
        (None, None),
    ],
)
def test_timestamps_become_utc(value, expected):
    assert timestamp(value) == expected


def test_a_many_to_one_reference_with_two_links_is_refused():
    change = Change(
        entity="stemming",
        id="s1",
        resume_token=1,
        api_updated="2026-09-01T00:00:00Z",
        source_updated="2026-09-01T02:00:00",
        deleted=False,
        fields={"soort": "Voor"},
        refs={"besluit": ["b1", "b2"]},
    )

    with pytest.raises(ValueError, match="2 links in besluit_id"):
        from_feed(BY_NAME["Stemming"], change, "b", "t")
