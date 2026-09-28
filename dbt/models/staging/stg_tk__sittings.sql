with latest as ({{ latest_versions('activiteit_changes') }})

select
    id as sitting_id,
    soort as sitting_type_nl,
    nummer as number,
    onderwerp as subject,
    datum_soort as date_kind,
    datum as sitting_at,
    aanvangstijd as starts_at,
    eindtijd as ends_at,
    besloten as is_closed_session,
    status,
    vergaderjaar as parliamentary_year,
    kamer as chamber,
    voortouwnaam as lead_committee,
    voortouwafkorting as lead_committee_abbreviation,
    source_updated
from latest
