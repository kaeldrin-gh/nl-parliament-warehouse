with latest as ({{ latest_versions('besluit_changes') }})

select
    id as decision_id,
    agendapunt_id as agenda_item_id,
    stemmings_soort as vote_method_nl,
    besluit_soort as decision_type_nl,
    besluit_tekst as decision_text,
    opmerking as remark,
    status,
    agendapunt_zaak_besluit_volgorde as position_in_agenda_item,
    zaak_ids as case_ids,
    source_updated
from latest
