-- One decision, dated by its sitting. Only decisions taken since the scope
-- start: the change feed also carries edits to older records.
select
    decisions.decision_id,
    decisions.agenda_item_id,
    agenda.sitting_id,
    {{ local_date('sittings.sitting_at') }} as decided_on,
    sittings.parliamentary_year,
    case decisions.vote_method_nl
        when 'Met handopsteken' then 'show_of_hands'
        when 'Hoofdelijk' then 'roll_call'
        when 'Zonder stemming' then 'without_vote'
    end as vote_method,
    decisions.decision_type_nl,
    case
        when decisions.decision_type_nl like 'Stemmen - aangenomen%' then 'accepted'
        when decisions.decision_type_nl like 'Stemmen - verworpen%' then 'rejected'
    end as outcome,
    decisions.decision_text,
    decisions.status
from {{ ref('stg_tk__decisions') }} as decisions
inner join {{ ref('stg_tk__agenda_items') }} as agenda
    on decisions.agenda_item_id = agenda.agenda_item_id
inner join {{ ref('stg_tk__sittings') }} as sittings
    on agenda.sitting_id = sittings.sitting_id
where {{ local_date('sittings.sitting_at') }} >= date '{{ var("scope_start") }}'
