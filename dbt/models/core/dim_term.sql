-- Parliamentary terms since the scope start. Installation dates are confirmed
-- by the data: new members' seats (stg_tk__seat_assignments.valid_from)
-- cluster on exactly these days.
select cast(2021 as int64) as term_id, date '2021-03-17' as election_date, date '2021-03-31' as installed_on, date '2023-12-05' as ended_on
union all
select cast(2023 as int64), date '2023-11-22', date '2023-12-06', date '2025-11-11'
union all
select cast(2025 as int64), date '2025-10-29', date '2025-11-12', cast(null as date)
