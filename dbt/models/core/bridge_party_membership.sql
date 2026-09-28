-- A member in a party seat for an interval. The source gives the interval
-- (valid time); the change log records when the source changed it.
select
    assignments.assignment_id,
    assignments.member_id,
    seats.party_id,
    assignments.seat_role,
    {{ local_date('assignments.valid_from') }} as valid_from,
    {{ local_date('assignments.valid_until') }} as valid_until
from {{ ref('stg_tk__seat_assignments') }} as assignments
inner join {{ ref('stg_tk__party_seats') }} as seats
    on assignments.seat_id = seats.seat_id
where assignments.valid_until is null
    or {{ local_date('assignments.valid_until') }} >= date '{{ var("scope_start") }}'
