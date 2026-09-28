with latest as ({{ latest_versions('zaak_changes') }})

select
    id as case_id,
    nummer as number,
    soort as case_type_nl,
    titel as title,
    citeertitel as citation_title,
    status,
    onderwerp as subject,
    gestart_op as started_at,
    organisatie as organisation,
    vergaderjaar as parliamentary_year,
    volgnummer as sequence_number,
    afgedaan as is_closed,
    huidige_behandelstatus as current_stage,
    source_updated
from latest
