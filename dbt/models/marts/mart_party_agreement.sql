-- For each pair of parties and month: on how many decisions both voted for or
-- against, and on how many of those they voted the same way. Counts, not
-- shares, so months add up to terms.
with took_part as (
    select decision_id, term_id, month_start, party, vote
    from {{ ref('int_party_votes_keyed') }}
    where vote in ('for', 'against')
)

select
    a.term_id,
    a.month_start,
    a.party as party_a,
    b.party as party_b,
    count(*) as decisions_both_voted,
    cast(sum(case when a.vote = b.vote then 1 else 0 end) as int64) as decisions_same_vote
from took_part as a
inner join took_part as b
    on a.decision_id = b.decision_id
    and a.party < b.party
group by a.term_id, a.month_start, a.party, b.party
