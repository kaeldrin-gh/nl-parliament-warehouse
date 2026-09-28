-- Same votes cannot exceed shared votes.
select *
from {{ ref('mart_party_agreement') }}
where decisions_same_vote > decisions_both_voted
