select
    party_id,
    abbreviation,
    name_nl,
    name_en,
    seats as seats_now,
    {{ local_date('active_from') }} as active_from,
    {{ local_date('active_until') }} as active_until
from {{ ref('stg_tk__parties') }}
