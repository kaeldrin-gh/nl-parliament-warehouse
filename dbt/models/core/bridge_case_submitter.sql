select
    case_actor_id,
    case_id,
    member_id,
    party_id,
    actor_name,
    actor_party,
    case relation_nl
        when 'Indiener' then 'submitter'
        when 'Medeindiener' then 'co_submitter'
    end as relation
from {{ ref('stg_tk__case_actors') }}
where relation_nl in ('Indiener', 'Medeindiener')
