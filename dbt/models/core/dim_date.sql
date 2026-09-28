with days as ({{ date_spine(var('scope_start')) }})

select
    days.date_day,
    cast(extract(year from days.date_day) as int64) as year,
    cast(extract(month from days.date_day) as int64) as month,
    {{ iso_year('days.date_day') }} as iso_year,
    {{ iso_week('days.date_day') }} as iso_week,
    {{ iso_day_of_week('days.date_day') }} as iso_day_of_week,
    {{ iso_day_of_week('days.date_day') }} >= 6 as is_weekend,
    terms.term_id
from days
left join {{ ref('dim_term') }} as terms
    on days.date_day >= terms.installed_on
    and (terms.ended_on is null or days.date_day <= terms.ended_on)
