drop view if exists stg_agent_activity;

create view stg_agent_activity as
select
    agent_id_hash,
    date(activity_date) as activity_date,
    upper(country_code) as country_code,
    cast(scheduled_minutes as integer) as scheduled_minutes,
    cast(available_minutes as integer) as available_minutes,
    cast(handled_contacts as integer) as handled_contacts,
    datetime(updated_at) as updated_at
from raw_agent_activity
where agent_id_hash is not null
  and activity_date is not null;
