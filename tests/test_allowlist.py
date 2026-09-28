"""Personal data outside the allowlist is never requested, parsed into rows, or written."""

from ingest.entities import ENTITIES, METADATA
from ingest.records import from_feed, odata_query
from ingest.syncfeed import parse_page

# Person fields the source publishes that this warehouse must never hold.
FORBIDDEN_PERSON_FIELDS = {
    "Voornamen",
    "Geslacht",
    "Geboortedatum",
    "Geboorteplaats",
    "Geboorteland",
    "Overlijdensdatum",
    "Overlijdensplaats",
    "Woonplaats",
    "Land",
}
FORBIDDEN_ENTITIES = {
    "PersoonGeschenk",
    "PersoonReis",
    "PersoonNevenfunctie",
    "PersoonContactinformatie",
    "PersoonLoopbaan",
    "PersoonOnderwijs",
}


def test_no_forbidden_entity_is_loaded():
    assert not {e.name for e in ENTITIES} & FORBIDDEN_ENTITIES


def test_person_columns_exclude_private_fields():
    person = next(e for e in ENTITIES if e.name == "Persoon")

    assert not {c.source for c in person.columns} & FORBIDDEN_PERSON_FIELDS


def test_odata_requests_select_only_allowlisted_person_fields():
    person = next(e for e in ENTITIES if e.name == "Persoon")

    selected = set(odata_query(person)["$select"].split(","))

    assert not selected & FORBIDDEN_PERSON_FIELDS
    assert selected == {c.source for c in METADATA if c.source} | {c.source for c in person.columns}


def test_a_feed_entry_with_private_fields_lands_without_them():
    person = next(e for e in ENTITIES if e.name == "Persoon")
    feed = """<feed xmlns="http://www.w3.org/2005/Atom"
        xmlns:tk="http://www.tweedekamer.nl/xsd/tkData/v1-0"><entry>
      <updated>2026-09-01T00:00:00Z</updated>
      <link rel="next" href="https://x/Feed?skiptoken=9&amp;category=Persoon" />
      <content type="application/xml"><tk:persoon id="p1" tk:bijgewerkt="2026-09-01T02:00:00"
          tk:verwijderd="false">
        <tk:achternaam>Jansen</tk:achternaam><tk:roepnaam>Anna</tk:roepnaam>
        <tk:geboortedatum>1980-01-01</tk:geboortedatum><tk:woonplaats>Utrecht</tk:woonplaats>
        <tk:geslacht>vrouw</tk:geslacht>
      </tk:persoon></content></entry></feed>"""
    (change,) = parse_page(feed).changes

    row = from_feed(person, change, "b", "t")

    assert row["achternaam"] == "Jansen" and row["roepnaam"] == "Anna"
    assert not {"geboortedatum", "woonplaats", "geslacht"} & set(row)
    assert "1980-01-01" not in row.values() and "Utrecht" not in row.values()


def test_column_names_are_unique_per_table():
    for entity in ENTITIES:
        names = [c.name for c in METADATA + entity.columns]
        assert len(names) == len(set(names)), entity.name
