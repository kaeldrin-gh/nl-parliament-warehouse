select
    case_id,
    number,
    case_type_nl,
    case case_type_nl
        when 'Motie' then 'motion'
        when 'Amendement' then 'amendment'
        when 'Wetgeving' then 'bill'
        when 'Initiatiefwetgeving' then 'private_member_bill'
        when 'Begroting' then 'budget'
        else 'other'
    end as case_type,
    title,
    subject,
    status,
    {{ local_date('started_at') }} as started_on,
    parliamentary_year,
    is_closed,
    current_stage
from {{ ref('stg_tk__cases') }}
