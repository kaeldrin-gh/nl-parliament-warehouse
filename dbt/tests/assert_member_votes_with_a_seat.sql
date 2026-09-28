{{ config(severity='warn') }}
-- A member voting in a roll call held a House seat that day. Warn only: the
-- source publishes no seat history for some members (docs/data-quality.md).
select vote_id, member_id, decided_on
from {{ ref('fct_member_vote') }}
where seat_party_id is null
