-- One row of headline counts for the report and the README.
with party_votes as (
    select
        count(*) as party_votes,
        count(distinct decision_id) as decisions_voted,
        min(decided_on) as first_vote_on,
        max(decided_on) as last_vote_on
    from {{ ref('fct_party_vote') }}
),

roll_calls as (
    select count(*) as member_votes, count(distinct decision_id) as roll_call_decisions
    from {{ ref('fct_member_vote') }}
),

latest as (
    select {{ local_date('max(source_updated)') }} as latest_source_change_on
    from {{ ref('stg_tk__votes') }}
)

select
    party_votes.decisions_voted,
    party_votes.party_votes,
    roll_calls.roll_call_decisions,
    roll_calls.member_votes,
    party_votes.first_vote_on,
    party_votes.last_vote_on,
    latest.latest_source_change_on
from party_votes
cross join roll_calls
cross join latest
