"""The feed parser against a real SyncFeed page (CC0, trimmed to five entries)."""

from pathlib import Path

import pytest

from ingest.syncfeed import parse_page

FIXTURE = Path(__file__).parent / "fixtures" / "syncfeed" / "stemming_page.xml"


@pytest.fixture(scope="module")
def page():
    return parse_page(FIXTURE.read_bytes())


def test_reads_every_entry_and_marks_tombstones(page):
    assert len(page.changes) == 5
    assert [c.deleted for c in page.changes].count(True) == 2
    assert {c.entity for c in page.changes} == {"stemming"}


def test_a_tombstone_carries_identity_but_no_fields(page):
    tombstone = next(c for c in page.changes if c.deleted)

    assert tombstone.id == "45d46c2d-aece-47b0-8358-523f5a56c1ee"
    assert tombstone.fields == {}
    assert tombstone.resume_token == 3547906


def test_a_live_vote_keeps_values_references_and_nulls(page):
    vote = next(c for c in page.changes if c.id == "80769453-41f8-4e01-8a10-f9da650fe3cb")

    assert not vote.deleted
    assert vote.fields["soort"] == "Tegen"
    assert vote.fields["actorFractie"] == "PVV"
    assert vote.fields["fractieGrootte"] == "9"
    assert vote.fields["vergissing"] == "false"
    assert vote.fields["besluit_id"] == "643f76ba-2d42-4d6f-b903-d71b0927144a"
    assert vote.fields["fractie_id"] == "65129918-f256-4975-9da4-488da34d6695"
    assert vote.fields["sidActorLid"] is None
    assert vote.source_updated == "2008-11-12T14:40:12.1730000"


def test_resume_tokens_only_move_forward(page):
    tokens = [c.resume_token for c in page.changes]

    assert tokens == sorted(tokens)
    assert len(set(tokens)) == len(tokens)


def test_page_points_to_the_next_page(page):
    assert page.next_token == 3560496


def test_the_end_of_the_feed_is_an_empty_page_without_a_next_link():
    empty = '<feed xmlns="http://www.w3.org/2005/Atom"><title>end</title></feed>'

    result = parse_page(empty)

    assert result.changes == []
    assert result.next_token is None
