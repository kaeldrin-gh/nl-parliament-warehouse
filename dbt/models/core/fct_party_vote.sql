-- One party's vote on one decision. A vote row without a member is a party
-- vote; with a member it is part of a roll call (fct_member_vote).
select
    votes.vote_id,
    votes.decision_id,
    votes.party_id,
    decisions.decided_on,
    votes.vote,
    votes.party_size,
    votes.is_mistake
from {{ ref('stg_tk__votes') }} as votes
inner join {{ ref('dim_decision') }} as decisions
    on votes.decision_id = decisions.decision_id
where votes.member_id is null
