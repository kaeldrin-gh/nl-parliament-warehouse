-- Everyone who held a House seat, cast an individual vote, or submitted a case
-- inside the scope. About a third of the source's person records arrive with
-- every field empty (docs/data-quality.md); for those, the name comes from the
-- votes or cases that mention the person.
with seat_holders as (
    select member_id, cast(null as string) as name_elsewhere
    from {{ ref('bridge_party_membership') }}
),

voters as (
    select member_id, actor_name as name_elsewhere
    from {{ ref('stg_tk__votes') }}
    where member_id is not null
),

submitters as (
    select member_id, actor_name as name_elsewhere
    from {{ ref('stg_tk__case_actors') }}
    where member_id is not null
),

in_scope as (
    select member_id, max(name_elsewhere) as name_elsewhere
    from (
        select * from seat_holders
        union all
        select * from voters
        union all
        select * from submitters
    ) as mentions
    group by member_id
)

select
    members.member_id,
    members.member_number,
    coalesce(
        nullif(
            trim(
                coalesce(members.first_name, members.initials, '')
                || ' ' || coalesce(members.surname_prefix || ' ', '')
                || coalesce(members.surname, '')
            ),
            ''
        ),
        in_scope.name_elsewhere
    ) as display_name,
    members.surname,
    members.party_label as party_label_now,
    members.current_role,
    members.surname is not null as has_source_profile
from {{ ref('stg_tk__members') }} as members
inner join in_scope
    on members.member_id = in_scope.member_id
