select
    decisions.decision_id,
    case_id
from {{ ref('stg_tk__decisions') }} as decisions,
    {{ unnest_as('decisions.case_ids', 'case_id') }}
where decisions.decision_id in (select decision_id from {{ ref('dim_decision') }})
