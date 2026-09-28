-- A party votes once per decision.
select decision_id, party_id, count(*) as votes
from {{ ref('fct_party_vote') }}
group by decision_id, party_id
having count(*) > 1
