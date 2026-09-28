with latest as ({{ latest_versions('fractie_changes') }})

select
    id as party_id,
    nummer as party_number,
    afkorting as abbreviation,
    naam_nl as name_nl,
    naam_en as name_en,
    aantal_zetels as seats,
    datum_actief as active_from,
    datum_inactief as active_until,
    source_updated
from latest
