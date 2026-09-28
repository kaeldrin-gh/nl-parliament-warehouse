with latest as ({{ latest_versions('fractie_zetel_persoon_changes') }})

select
    id as assignment_id,
    fractie_zetel_id as seat_id,
    persoon_id as member_id,
    functie as seat_role,
    van as valid_from,
    tot_en_met as valid_until,
    source_updated
from latest
