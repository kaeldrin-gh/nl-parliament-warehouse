-- Decisions that were put to a vote, by month and case type, and how they ended.
select
    dates.term_id,
    cast({{ dbt.date_trunc('month', 'decisions.decided_on') }} as date) as month_start,
    cases.case_type,
    cast(sum(case when decisions.outcome = 'accepted' then 1 else 0 end) as int64) as accepted,
    cast(sum(case when decisions.outcome = 'rejected' then 1 else 0 end) as int64) as rejected
from {{ ref('dim_decision') }} as decisions
inner join {{ ref('bridge_decision_case') }} as links
    on decisions.decision_id = links.decision_id
inner join {{ ref('dim_case') }} as cases
    on links.case_id = cases.case_id
inner join {{ ref('dim_date') }} as dates
    on decisions.decided_on = dates.date_day
where decisions.outcome is not null
group by dates.term_id, month_start, cases.case_type
