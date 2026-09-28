-- One member's vote in a roll call (vote_method = 'roll_call'). party_id is
-- the party the source recorded on the vote; seat_party_id is the party whose
-- seat the member held that day, from bridge_party_membership (valid time).
-- They differ when the source reuses an old party record (docs/data-quality.md).
with votes as (
    select
        votes.vote_id,
        votes.decision_id,
        votes.member_id,
        votes.party_id,
        decisions.decided_on,
        votes.vote,
        votes.is_mistake
    from {{ ref('stg_tk__votes') }} as votes
    inner join {{ ref('dim_decision') }} as decisions
        on votes.decision_id = decisions.decision_id
    where votes.member_id is not null
),

seat_that_day as (
    select votes.vote_id, min(seats.party_id) as seat_party_id
    from votes
    inner join {{ ref('bridge_party_membership') }} as seats
        on votes.member_id = seats.member_id
        and votes.decided_on >= seats.valid_from
        and (seats.valid_until is null or votes.decided_on <= seats.valid_until)
    group by votes.vote_id
)

select
    votes.vote_id,
    votes.decision_id,
    votes.member_id,
    votes.party_id,
    seat_that_day.seat_party_id,
    votes.decided_on,
    votes.vote,
    votes.is_mistake
from votes
left join seat_that_day
    on votes.vote_id = seat_that_day.vote_id
