"""The report payload and page, from mart rows and without a warehouse."""

import json
import re
from datetime import date

from report.build import MIN_SHARED, render, shape

OVERVIEW = {
    "decisions_voted": 3,
    "party_votes": 6,
    "roll_call_decisions": 1,
    "member_votes": 150,
    "first_vote_on": date(2025, 11, 13),
    "last_vote_on": date(2026, 9, 24),
    "latest_source_change_on": date(2026, 9, 25),
}


def participation(term, party, decisions=100, took_part=99):
    return {
        "term_id": term,
        "party": party,
        "decisions": decisions,
        "took_part": took_part,
        "not_voted": decisions - took_part,
        "declared_mistakes": 0,
        "last_month": date(2026, 9, 1),
    }


def payload(**overrides):
    rows = {
        "overview": OVERVIEW,
        "participation": [
            participation(2025, "Small"),
            participation(2025, "Big"),
            participation(2023, "Old"),
        ],
        "seats": [
            {"term_id": 2025, "party": "Small", "seats": 3},
            {"term_id": 2025, "party": "Big", "seats": 30},
            {"term_id": 2023, "party": "Old", "seats": 10},
        ],
        "agreement": [
            {
                "term_id": 2025,
                "party_a": "Big",
                "party_b": "Small",
                "both_voted": 40,
                "same_vote": 30,
            },
        ],
        "monthly": [{"month_start": date(2026, 6, 1), "accepted": 5, "rejected": 7}],
        "submitters": [{"term_id": 2025, "submitter_party": "Small", "accepted": 2, "rejected": 1}],
    }
    rows.update(overrides)
    return shape(**rows)


def test_terms_run_newest_first_with_parties_by_seats():
    result = payload()

    assert [t["term_id"] for t in result["terms"]] == [2025, 2023]
    assert result["terms"][0]["parties"] == ["Big", "Small"]


def test_agreement_is_symmetric_and_shares_are_computed_from_counts():
    cells = payload()["terms"][0]["cells"]

    assert {(c["a"], c["b"]) for c in cells} == {("Big", "Small"), ("Small", "Big")}
    assert {c["share"] for c in cells} == {0.75}


def test_too_few_shared_votes_leave_the_cell_blank():
    sparse = [
        {
            "term_id": 2025,
            "party_a": "Big",
            "party_b": "Small",
            "both_voted": MIN_SHARED - 1,
            "same_vote": MIN_SHARED - 1,
        }
    ]

    cells = payload(agreement=sparse)["terms"][0]["cells"]

    assert all(c["share"] is None for c in cells)


def test_motions_by_party_follow_the_seat_order_and_skip_parties_without_motions():
    motions = payload()["terms"][0]["motions_by_party"]

    assert motions == [{"party": "Small", "accepted": 2, "rejected": 1}]


def test_the_page_embeds_data_that_cannot_close_its_script_element():
    hostile = [participation(2025, "A</script><script>alert(1)</script>")]
    seats = [{"term_id": 2025, "party": hostile[0]["party"], "seats": 1}]

    page = render(payload(participation=hostile, seats=seats, agreement=[], submitters=[]))

    data = re.search(
        r'<script id="report-data" type="application/json">(.*?)</script>', page, re.S
    ).group(1)
    assert "</script>" not in data
    assert json.loads(data)["terms"][0]["parties"] == ["A</script><script>alert(1)</script>"]
    assert "<td>A&lt;/script&gt;" in page


def test_the_page_shows_headline_numbers_and_every_chart():
    page = render(payload())

    for chart in ["agreement", "monthly", "participation", "submitters"]:
        assert f'id="chart-{chart}"' in page
    assert "<div class='num'>3</div>" in page  # decisions put to a party vote
    assert "<div class='num'>24 Sep 2026</div>" in page  # latest vote
