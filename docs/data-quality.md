# Data quality findings

Problems found in the source data, with the evidence and what the warehouse
does about them. Each one is either fixed in a model or surfaced by a test
that warns instead of failing, because the data is what the source publishes.

Counts are from the BigQuery build on 28 September 2026.

## DQ-1: 50PLUS votes are recorded under a closed party record

**Evidence.** The source has two party records for 50PLUS: one active from
2012 until 11 May 2021, and one from 12 November 2025, when the party returned
to the House. Members' seats in the current term point to the new record, but
every 50PLUS vote since the term started points to the old one: 4,338 party
votes from 13 November 2025 to 24 September 2026, and the party's roll-call
votes.

**Handling.**

- `fct_party_vote.party_id` and `fct_member_vote.party_id` keep what the
  source recorded.
- `fct_member_vote.seat_party_id` adds the party whose seat the member held
  on the day, from `bridge_party_membership`, so roll-call analysis can use
  the party as it existed.
- `assert_votes_recorded_for_active_parties` warns on every vote recorded for
  a party record that was no longer active. Today it lists exactly these
  4,338 votes; a new party with the same problem would show up here too.

The marts key parties by abbreviation (`int_party_votes_keyed`), so the two
records count as one party, and the report says so in its notes.

## DQ-2: A third of person records are empty

**Evidence.** 1,374 of 4,477 person records come back from OData with every
field empty, including `GewijzigdOp` and `Verwijderd`. Most belong to people
outside the House, but 6 of them cast roll-call votes (248 votes), and the
source publishes no seat history for them. Their names appear only on the
votes themselves (for example "Nobel, J.N.J.").

**Handling.**

- `dim_member.display_name` falls back to the name recorded on the person's
  votes or cases when the record is empty; `has_source_profile` is false for
  those members.
- `fct_member_vote.seat_party_id` is empty for their votes, and
  `assert_member_votes_with_a_seat` warns on them (248 today).

## DQ-3: The two APIs disagree on when a change was published

**Evidence.** For the same change, the feed's Atom `updated` and OData's
`ApiGewijzigdOp` differ by about a second. The source's own change time
agrees: `tk:bijgewerkt` in the feed (Amsterdam local time, no offset) equals
`GewijzigdOp` in OData once converted to UTC.

**Handling.** Versions are ordered by `source_updated`, the source's change
time, so a snapshot row and a feed row compare correctly (see
[design.md](design.md), Ingestion). The dbt unit test
`latest_version_wins_and_deletions_disappear` covers the ordering rules.
