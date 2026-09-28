with latest as ({{ latest_versions('stemming_changes') }})

select
    id as vote_id,
    besluit_id as decision_id,
    persoon_id as member_id,
    fractie_id as party_id,
    case soort
        when 'Voor' then 'for'
        when 'Tegen' then 'against'
        when 'Niet deelgenomen' then 'not_voted'
    end as vote,
    soort as vote_nl,
    fractie_grootte as party_size,
    actor_naam as actor_name,
    actor_fractie as actor_party,
    vergissing as is_mistake,
    source_updated
from latest
