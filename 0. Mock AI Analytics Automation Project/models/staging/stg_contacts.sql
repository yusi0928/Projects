drop view if exists stg_contacts;

create view stg_contacts as
select
    contact_id,
    order_id,
    customer_id_hash,
    agent_id_hash,
    upper(country_code) as country_code,
    lower(contact_reason_id) as contact_reason_id,
    datetime(created_at) as created_at,
    nullif(datetime(resolved_at), '') as resolved_at,
    lower(status) as status,
    cast(reopened_flag as integer) as reopened_flag,
    cast(handling_time_seconds as integer) as handling_time_seconds,
    datetime(updated_at) as updated_at
from raw_contacts
where contact_id is not null
  and created_at is not null;
