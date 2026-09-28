-- Keying parties by abbreviation must not give one party two votes on the same
-- decision; if two records of one party ever vote on the same decision, the
-- agreement mart would double count.
select decision_id, party, count(*) as votes
from {{ ref('int_party_votes_keyed') }}
group by decision_id, party
having count(*) > 1
