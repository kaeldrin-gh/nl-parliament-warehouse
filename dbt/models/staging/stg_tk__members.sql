-- Public-role fields only; the loader never requests the rest (ingest/entities.py).
with latest as ({{ latest_versions('persoon_changes') }})

select
    id as member_id,
    nummer as member_number,
    initialen as initials,
    roepnaam as first_name,
    tussenvoegsel as surname_prefix,
    achternaam as surname,
    functie as current_role,
    fractielabel as party_label,
    source_updated
from latest
