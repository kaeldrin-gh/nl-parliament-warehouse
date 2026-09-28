with latest as ({{ latest_versions('zaak_actor_changes') }})

select
    id as case_actor_id,
    zaak_id as case_id,
    persoon_id as member_id,
    fractie_id as party_id,
    commissie_id as committee_id,
    actor_naam as actor_name,
    actor_fractie as actor_party,
    actor_afkorting as actor_abbreviation,
    functie as actor_role,
    relatie as relation_nl,
    source_updated
from latest
