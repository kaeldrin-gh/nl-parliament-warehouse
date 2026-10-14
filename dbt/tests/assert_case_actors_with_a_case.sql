{{ config(severity='warn') }}
-- A submitter or co-signer belongs to a case in dim_case. Warn only:
-- bridge_case_submitter drops these rows, and a case created during the run
-- arrives with the next one (docs/operations.md).
select actors.case_actor_id, actors.case_id, actors.relation_nl, actors.source_updated
from {{ ref('stg_tk__case_actors') }} as actors
where actors.relation_nl in ('Indiener', 'Medeindiener')
    and actors.case_id not in (select case_id from {{ ref('dim_case') }})
