with latest as ({{ latest_versions('agendapunt_changes') }})

select
    id as agenda_item_id,
    activiteit_id as sitting_id,
    nummer as number,
    onderwerp as subject,
    aanvangstijd as starts_at,
    eindtijd as ends_at,
    volgorde as position,
    rubriek as section,
    status,
    source_updated
from latest
