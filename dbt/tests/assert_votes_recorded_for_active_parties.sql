{{ config(severity='warn') }}
-- A vote is recorded for a party that was active on the day. Warn only: the
-- source sometimes records votes for an older record of the same party
-- (docs/data-quality.md).
select votes.vote_id, parties.abbreviation, parties.active_until, votes.decided_on
from {{ ref('fct_party_vote') }} as votes
inner join {{ ref('dim_party') }} as parties
    on votes.party_id = parties.party_id
where parties.active_until < votes.decided_on
