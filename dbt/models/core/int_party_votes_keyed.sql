-- Party votes keyed by party abbreviation rather than party record, so a party
-- that the source splits over two records counts as one (docs/data-quality.md,
-- DQ-1). Parties whose record has no abbreviation fall back to the name.
select
    votes.vote_id,
    votes.decision_id,
    dates.term_id,
    cast({{ dbt.date_trunc('month', 'votes.decided_on') }} as date) as month_start,
    coalesce(parties.abbreviation, parties.name_nl) as party,
    votes.vote,
    votes.party_size,
    votes.is_mistake
from {{ ref('fct_party_vote') }} as votes
inner join {{ ref('dim_party') }} as parties
    on votes.party_id = parties.party_id
inner join {{ ref('dim_date') }} as dates
    on votes.decided_on = dates.date_day
