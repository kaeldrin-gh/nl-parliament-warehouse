with latest as ({{ latest_versions('fractie_zetel_changes') }})

select
    id as seat_id,
    fractie_id as party_id,
    gewicht as weight,
    source_updated
from latest
