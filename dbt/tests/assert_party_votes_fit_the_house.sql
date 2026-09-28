-- The seats behind a decision's party votes cannot exceed the 150 seats of the House.
select decision_id, sum(party_size) as seats
from {{ ref('fct_party_vote') }}
group by decision_id
having sum(party_size) > 150
