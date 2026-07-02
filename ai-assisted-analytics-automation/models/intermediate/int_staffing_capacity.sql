drop view if exists int_staffing_capacity;

create view int_staffing_capacity as
select
    date(activity_date, '-' || ((cast(strftime('%w', activity_date) as integer) + 6) % 7) || ' days') as week_start,
    country_code,
    count(distinct agent_id_hash) as active_agents,
    sum(scheduled_minutes) as scheduled_minutes,
    sum(available_minutes) as available_minutes,
    sum(handled_contacts) as handled_contacts
from stg_agent_activity
group by 1,2;
