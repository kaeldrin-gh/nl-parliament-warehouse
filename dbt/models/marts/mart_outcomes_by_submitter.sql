-- Outcomes of voted decisions by the party of the case's first submitter
-- (indiener). A case submitted by members of two parties counts for both, so
-- these rows do not add up to mart_outcomes_monthly.
with submitter_parties as (
    select distinct case_id, coalesce(actor_party, 'no party recorded') as submitter_party
    from {{ ref('bridge_case_submitter') }}
    where relation = 'submitter'
)

select
    dates.term_id,
    submitters.submitter_party,
    cases.case_type,
    cast(sum(case when decisions.outcome = 'accepted' then 1 else 0 end) as int64) as accepted,
    cast(sum(case when decisions.outcome = 'rejected' then 1 else 0 end) as int64) as rejected
from {{ ref('dim_decision') }} as decisions
inner join {{ ref('bridge_decision_case') }} as links
    on decisions.decision_id = links.decision_id
inner join {{ ref('dim_case') }} as cases
    on links.case_id = cases.case_id
inner join submitter_parties as submitters
    on cases.case_id = submitters.case_id
inner join {{ ref('dim_date') }} as dates
    on decisions.decided_on = dates.date_day
where decisions.outcome is not null
group by dates.term_id, submitters.submitter_party, cases.case_type
