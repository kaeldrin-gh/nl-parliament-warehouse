-- A roll call has at most one vote per member and 150 members.
select decision_id, count(*) as votes, count(distinct member_id) as members
from {{ ref('fct_member_vote') }}
group by decision_id
having count(*) > 150 or count(*) <> count(distinct member_id)
