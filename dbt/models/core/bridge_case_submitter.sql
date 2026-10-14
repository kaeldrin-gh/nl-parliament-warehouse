-- Only cases in dim_case: a case actor can arrive without its case, for
-- example when the case was deleted, or created between the Zaak and ZaakActor
-- reads of one run. assert_case_actors_with_a_case warns on those rows.
select
    actors.case_actor_id,
    actors.case_id,
    actors.member_id,
    actors.party_id,
    actors.actor_name,
    actors.actor_party,
    case actors.relation_nl
        when 'Indiener' then 'submitter'
        when 'Medeindiener' then 'co_submitter'
    end as relation
from {{ ref('stg_tk__case_actors') }} as actors
where actors.relation_nl in ('Indiener', 'Medeindiener')
    and actors.case_id in (select case_id from {{ ref('dim_case') }})
