-- For each party and month: decisions put to a party vote, and how the party
-- took part in them.
select
    term_id,
    month_start,
    party,
    count(*) as decisions,
    cast(sum(case when vote in ('for', 'against') then 1 else 0 end) as int64) as took_part,
    cast(sum(case when vote = 'not_voted' then 1 else 0 end) as int64) as not_voted,
    cast(sum(case when is_mistake then 1 else 0 end) as int64) as declared_mistakes,
    max(party_size) as seats
from {{ ref('int_party_votes_keyed') }}
group by term_id, month_start, party
